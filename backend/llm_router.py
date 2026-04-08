# ============================================================
#  llm_router.py  —  Connects Groq + Gemini + Ollama
#  All three return the same dict structure so the rest of
#  the app doesn't need to know which LLM was used.
# ============================================================

import json
import re
import time
import requests
from typing import Optional

from config import (
    GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY,
    GROQ_MODELS, GEMINI_MODELS, OLLAMA_MODELS, OPENROUTER_MODELS,
    OLLAMA_BASE_URL,
)
from prompt_engine import SYSTEM_PROMPT, build_prompt


# ── Helpers ───────────────────────────────────────────────────

def _clean_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    # Remove ```json ... ``` fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    
    # Find the first { to skip any stray preamble
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1:
        raise ValueError(f"No JSON object found in response:\n{raw[:500]}")
    
    cleaned = cleaned[start:end]
    
    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fix common LLM JSON mistakes
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    # Fix unescaped newlines inside strings
    cleaned = re.sub(r'(?<!\\)\n', ' ', cleaned)
    # Fix unescaped quotes inside strings (basic)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort — try to extract just the questions array
    try:
        questions_match = re.search(r'"questions"\s*:\s*(\[.*?\])', cleaned, re.DOTALL)
        if questions_match:
            questions = json.loads(questions_match.group(1))
            return {
                "bloom_level":      1,
                "bloom_level_name": "Unknown",
                "topic":            "Unknown",
                "questions":        questions,
            }
    except Exception:
        pass

    raise ValueError(f"Could not parse JSON from response:\n{raw[:500]}")


def _provider_of(display_name: str) -> str:
    """Detect which provider owns a display-name model string."""
    if display_name in GROQ_MODELS:
        return "groq"
    if display_name in GEMINI_MODELS:
        return "gemini"
    if display_name in OLLAMA_MODELS:
        return "ollama"
    if display_name in OPENROUTER_MODELS:
        return "openrouter"
    raise ValueError(f"Unknown model: {display_name}")


# ── Groq ──────────────────────────────────────────────────────

def _call_groq(model_id: str, system: str, user: str) -> str:
    """
    Call Groq API (OpenAI-compatible).
    Free tier: 30 req/min, 14,400 req/day.
    """
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
        max_tokens=3000,
    )
    return response.choices[0].message.content


# ── Gemini ────────────────────────────────────────────────────

def _call_gemini(model_id: str, system: str, user: str) -> str:
    """
    Call Google Gemini API.
    Free tier: 15 req/min, 1,500 req/day (Flash models).
    """
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=model_id,
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=3000,
        ),
    )
    return response.text


# ── Ollama ────────────────────────────────────────────────────

def _call_ollama(model_id: str, system: str, user: str) -> str:
    """
    Call Ollama local API (must be running: `ollama serve`).
    No rate limit — runs on your hardware.
    Check available models: `ollama list`
    Pull a model: `ollama pull llama3.2`
    """
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 3000,
        },
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=120,          # local models can be slow
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]

def _call_openrouter(model_id: str, system: str, user: str) -> str:
    import requests
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "http://localhost:5173",
        },
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.7,
            "max_tokens":  3000,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ── Public router ─────────────────────────────────────────────

def generate_quiz(
    display_model: str,
    topic: str,
    context: str,
    bloom_level: int,
    num_questions: int = 3,
) -> dict:
    """
    Main entry point. Call this from app.py.

    Args:
        display_model  : key from GROQ_MODELS / GEMINI_MODELS / OLLAMA_MODELS
        topic          : subject of the questions
        context        : optional reference text (PDF content, article, etc.)
        bloom_level    : 1–6
        num_questions  : how many questions to generate

    Returns:
        {
            "bloom_level": int,
            "bloom_level_name": str,
            "topic": str,
            "questions": [ {...}, ... ],
            "provider": "groq" | "gemini" | "ollama",
            "model": str,
            "latency_sec": float,
        }
    """
    provider = _provider_of(display_model)

    # Resolve display name → actual API model id
    all_models = {**GROQ_MODELS, **GEMINI_MODELS, **OLLAMA_MODELS, **OPENROUTER_MODELS}
    model_id   = all_models[display_model]

    system_msg = SYSTEM_PROMPT
    user_msg   = build_prompt(topic, context, bloom_level, num_questions)

    start = time.time()

    if provider == "groq":
        raw = _call_groq(model_id, system_msg, user_msg)
    elif provider == "gemini":
        raw = _call_gemini(model_id, system_msg, user_msg)
    elif provider == "ollama":
        raw = _call_ollama(model_id, system_msg, user_msg)
    elif provider == "openrouter":
        raw = _call_openrouter(model_id, system_msg, user_msg)

    latency = round(time.time() - start, 2)

    result         = _clean_json(raw)
    result["provider"]    = provider
    result["model"]       = display_model
    result["latency_sec"] = latency
    return result


def check_ollama_status() -> tuple[bool, list[str]]:
    """
    Returns (is_running, list_of_available_models).
    Used by the UI to show which local models are ready.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        models = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        return True, models
    except Exception:
        return False, []


def check_groq_status() -> bool:
    """Quick key validation — returns True if key looks set."""
    return bool(GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here")


def check_gemini_status() -> bool:
    """Quick key validation — returns True if key looks set."""
    return bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")
