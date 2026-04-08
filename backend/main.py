# ============================================================
#  main.py  —  FastAPI backend  (v2 — full research edition)
#  Run: uvicorn main:app --reload --port 8000
# ============================================================

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from config       import GROQ_MODELS, GEMINI_MODELS, OLLAMA_MODELS, BLOOM_LEVELS, OPENROUTER_MODELS, OPENROUTER_API_KEY
from llm_router   import generate_quiz, check_ollama_status, check_groq_status, check_gemini_status
from pdf_parser   import extract_text_from_pdf, chunk_text
from database     import (
    init_db, save_session, save_scores, get_all_sessions,
    get_session_detail, save_evaluation, get_evaluation_table,
    save_comparison, get_analytics_summary,
)
from bloom_classifier import evaluate_quiz_result, classify_question_heuristic, evaluate_questions_detailed
from evaluation_logger import append_generation_rows
from google_drive import (
    is_configured  as drive_configured,
    save_quiz_session      as drive_save_session,
    save_evaluation_result as drive_save_evaluation,
    save_export            as drive_save_export,
    list_saved_sessions    as drive_list_sessions,
)

app = FastAPI(title="Bloom Quiz Research API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── Status ────────────────────────────────────────────────────
@app.get("/api/status")
def get_status():
    ollama_ok, ollama_models = check_ollama_status()
    return {
        "groq":          check_groq_status(),
        "gemini":        check_gemini_status(),
        "ollama":        ollama_ok,
        "ollama_models": ollama_models,
        "drive":         drive_configured(),
    }


# ── Models + Bloom levels ─────────────────────────────────────
@app.get("/api/models")
def get_models():
    from config import OPENROUTER_MODELS, OPENROUTER_API_KEY
    ollama_ok, ollama_models = check_ollama_status()
    models = []

    if check_groq_status():
        for name in GROQ_MODELS:
            models.append({"label": name, "provider": "groq"})

    if check_gemini_status():
        for name in GEMINI_MODELS:
            models.append({"label": name, "provider": "gemini"})

    if ollama_ok:
        for name, mid in OLLAMA_MODELS.items():
            base = mid.split(":")[0]
            if not ollama_models or any(m.startswith(base) for m in ollama_models):
                models.append({"label": name, "provider": "ollama"})

    if OPENROUTER_API_KEY and "sk-or" in OPENROUTER_API_KEY:
        for name in OPENROUTER_MODELS:
            models.append({"label": name, "provider": "openrouter"})

    return {"models": models}


@app.get("/api/bloom-levels")
def get_bloom_levels():
    return {"levels": [
        {"level": k, "name": v["name"], "color": v["color"],
         "description": v["description"], "verbs": v["verbs"]}
        for k, v in BLOOM_LEVELS.items()
    ]}


# ── PDF upload ────────────────────────────────────────────────
@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted.")
    try:
        class _W:
            def __init__(self, b, n): self._b = b; self.name = n
            def read(self): return self._b
            def seek(self, n): pass
        raw = await file.read()
        text, pages = extract_text_from_pdf(_W(raw, file.filename))
        chunk = chunk_text(text)
        return {"filename": file.filename, "pages": pages, "char_count": len(chunk), "text": chunk}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Generate (single LLM) ─────────────────────────────────────
class GenerateRequest(BaseModel):
    model:         str
    topic:         str
    bloom_level:   int
    num_questions: int            = 3
    difficulty:    str            = "medium"
    context:       Optional[str] = ""


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required.")
    if req.bloom_level not in range(1, 7):
        raise HTTPException(400, "Bloom level must be 1-6.")
    try:
        result = generate_quiz(
            display_model=req.model,
            topic=req.topic,
            context=req.context or "",
            bloom_level=req.bloom_level,
            num_questions=req.num_questions,
        )
        result["evaluation"] = evaluate_quiz_result(result, req.bloom_level, context=req.context or "")
        result["question_evaluations"] = evaluate_questions_detailed(
            result, requested_level=req.bloom_level, context=req.context or ""
        )
        result["difficulty"]  = req.difficulty

        session_id = save_session(result)
        result["session_id"] = session_id

        result["csv_log"] = append_generation_rows(
            result=result,
            endpoint="/api/generate",
            requested_level=req.bloom_level,
            context=req.context or "",
            session_id=session_id,
            run_id=f"session-{session_id}",
        )

        if drive_configured():
            dr = drive_save_session(result)
            result["drive_link"] = dr.get("link")

        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Multi-level quiz builder ──────────────────────────────────
class LevelSpec(BaseModel):
    level:      int
    count:      int
    difficulty: str = "medium"


class MultiLevelRequest(BaseModel):
    model:   str
    topic:   str
    context: Optional[str] = ""
    levels:  List[LevelSpec]


@app.post("/api/generate/multi-level")
def generate_multi_level(req: MultiLevelRequest):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required.")

    all_questions  = []
    meta_per_level = []
    total_latency  = 0.0

    for spec in req.levels:
        if spec.count == 0:
            continue
        try:
            r = generate_quiz(
                display_model=req.model,
                topic=req.topic,
                context=req.context or "",
                bloom_level=spec.level,
                num_questions=spec.count,
            )
            offset = len(all_questions)
            for i, q in enumerate(r.get("questions", [])):
                q["id"]          = offset + i + 1
                q["bloom_level"] = spec.level
                q["bloom_name"]  = BLOOM_LEVELS[spec.level]["name"]
                q["bloom_color"] = BLOOM_LEVELS[spec.level]["color"]
                all_questions.append(q)

            ev = evaluate_quiz_result(r, spec.level, context=req.context or "")
            total_latency += r.get("latency_sec", 0)
            meta_per_level.append({
                "level":               spec.level,
                "name":                BLOOM_LEVELS[spec.level]["name"],
                "color":               BLOOM_LEVELS[spec.level]["color"],
                "count":               len(r.get("questions", [])),
                "classifier_accuracy": ev["classifier_accuracy"],
                "avg_quality":         ev["avg_question_quality"],
                "latency_sec":         r.get("latency_sec", 0),
            })
        except Exception as e:
            meta_per_level.append({"level": spec.level, "error": str(e)})

    combined = {
        "topic":           req.topic,
        "model":           req.model,
        "type":            "multi_level",
        "total_questions": len(all_questions),
        "total_latency":   round(total_latency, 2),
        "questions":       all_questions,
        "level_summary":   meta_per_level,
        "bloom_level":     0,
        "bloom_level_name":"Multi",
        "provider":        "",
    }

    combined["session_id"] = save_session(combined)
    combined["question_evaluations"] = evaluate_questions_detailed(
        combined, requested_level=None, context=req.context or ""
    )
    combined["csv_log"] = append_generation_rows(
        result=combined,
        endpoint="/api/generate/multi-level",
        requested_level=None,
        context=req.context or "",
        session_id=combined["session_id"],
        run_id=f"session-{combined['session_id']}",
    )

    if drive_configured():
        dr = drive_save_session(combined)
        combined["drive_link"] = dr.get("link")

    return combined


# ── Side-by-side LLM comparison ──────────────────────────────
class CompareRequest(BaseModel):
    models:        List[str]
    topic:         str
    bloom_level:   int
    num_questions: int            = 2
    difficulty:    str            = "medium"
    context:       Optional[str] = ""


@app.post("/api/generate/compare")
def generate_compare(req: CompareRequest):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required.")
    if len(req.models) < 2:
        raise HTTPException(400, "Select at least 2 models to compare.")

    results = {}
    for model in req.models:
        try:
            r = generate_quiz(
                display_model=model,
                topic=req.topic,
                context=req.context or "",
                bloom_level=req.bloom_level,
                num_questions=req.num_questions,
            )
            r["evaluation"] = evaluate_quiz_result(r, req.bloom_level, context=req.context or "")
            r["question_evaluations"] = evaluate_questions_detailed(
                r, requested_level=req.bloom_level, context=req.context or ""
            )
            results[model]  = r
        except Exception as e:
            results[model] = {"error": str(e)}

    comparison = {
        "topic":       req.topic,
        "bloom_level": req.bloom_level,
        "bloom_name":  BLOOM_LEVELS[req.bloom_level]["name"],
        "difficulty":  req.difficulty,
        "models":      req.models,
        "results":     results,
    }

    comparison["comparison_id"] = save_comparison(comparison)

    for model_name, model_result in results.items():
        if "error" in model_result:
            continue
        model_result["csv_log"] = append_generation_rows(
            result=model_result,
            endpoint="/api/generate/compare",
            requested_level=req.bloom_level,
            context=req.context or "",
            session_id=None,
            run_id=f"compare-{comparison['comparison_id']}-{model_name}",
        )

    if drive_configured():
        dr = drive_save_evaluation(comparison)
        comparison["drive_link"] = dr.get("link")

    return comparison


# ── Submit scores ─────────────────────────────────────────────
class ScoreItem(BaseModel):
    question_id:    int
    question_text:  str
    bloom_level:    int
    selected_ans:   Optional[str]
    correct_ans:    str
    is_correct:     bool
    time_taken_sec: Optional[float]


class ScoreRequest(BaseModel):
    session_id: int
    scores:     List[ScoreItem]


@app.post("/api/scores")
def submit_scores(req: ScoreRequest):
    save_scores(req.session_id, [s.dict() for s in req.scores])
    return {"saved": True}


# ── Bloom auto-detector ───────────────────────────────────────
class DetectRequest(BaseModel):
    question: str


@app.post("/api/detect-bloom")
def detect_bloom(req: DetectRequest):
    return classify_question_heuristic(req.question)


# ── History + analytics ───────────────────────────────────────
@app.get("/api/history")
def get_history(limit: int = 50):
    return {"sessions": get_all_sessions(limit)}


@app.get("/api/history/{session_id}")
def get_session(session_id: int):
    s = get_session_detail(session_id)
    if not s:
        raise HTTPException(404, "Session not found.")
    return s


@app.get("/api/analytics")
def get_analytics():
    return {
        "summary":          get_analytics_summary(),
        "evaluation_table": get_evaluation_table(),
    }


# ── Google Drive ──────────────────────────────────────────────
@app.get("/api/drive/status")
def drive_status():
    return {
        "configured": drive_configured(),
        "files":      drive_list_sessions() if drive_configured() else [],
    }


@app.post("/api/drive/export-all")
def export_all_to_drive():
    import datetime
    payload = {
        "exported_at":      datetime.datetime.now().isoformat(),
        "sessions":         get_all_sessions(500),
        "evaluation_table": get_evaluation_table(),
        "analytics":        get_analytics_summary(),
    }
    if not drive_configured():
        return {"saved": False, "error": "Google Drive not configured. Add service_account.json"}
    result = drive_save_export(payload, "full_research_export")
    return {"saved": True, "link": result.get("link"), "total": len(payload["sessions"])}


from fastapi.responses import JSONResponse

@app.get("/api/download/all-sessions")
def download_all_sessions():
    sessions  = get_all_sessions(500)
    analytics = get_analytics_summary()
    eval_table = get_evaluation_table()
    return JSONResponse({
        "total_sessions":   len(sessions),
        "sessions":         sessions,
        "analytics":        analytics,
        "evaluation_table": eval_table,
    })
