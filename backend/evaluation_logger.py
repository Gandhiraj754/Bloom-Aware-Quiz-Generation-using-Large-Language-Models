import csv
import os
from datetime import datetime
from typing import Optional

from bloom_classifier import evaluate_question_item


EXPORT_DIR = os.path.join(os.path.dirname(__file__), "evaluation_exports")
CSV_PATH = os.path.join(EXPORT_DIR, "generated_questions_log.csv")


def _ensure_export_path() -> None:
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _ensure_csv_header() -> None:
    _ensure_export_path()
    if os.path.exists(CSV_PATH):
        return

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_csv_headers())
        writer.writeheader()


def _csv_headers() -> list[str]:
    return [
        "timestamp",
        "endpoint",
        "run_id",
        "session_id",
        "topic",
        "model",
        "provider",
        "requested_bloom_level",
        "question_id",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_answer_key",
        "correct_answer_text",
        "predicted_level",
        "classifier_confidence",
        "level_match",
        "quality_score",
        "relevance_score",
        "overall_score",
        "latency_sec",
    ]


def append_generation_rows(
    *,
    result: dict,
    endpoint: str,
    requested_level: Optional[int],
    context: str = "",
    session_id: Optional[int] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Append one CSV row per generated question.
    Returns metadata about the write for API responses.
    """
    _ensure_csv_header()

    now = datetime.now().isoformat()
    run_id = run_id or f"run-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    rows = []

    for q in result.get("questions", []):
        level = requested_level if requested_level else q.get("bloom_level", result.get("bloom_level", 1))
        ev = evaluate_question_item(q, level, context=context)
        options = q.get("options", {})
        correct_key = q.get("correct_answer")

        rows.append({
            "timestamp": now,
            "endpoint": endpoint,
            "run_id": run_id,
            "session_id": session_id,
            "topic": result.get("topic", ""),
            "model": result.get("model", ""),
            "provider": result.get("provider", ""),
            "requested_bloom_level": level,
            "question_id": q.get("id"),
            "question_text": q.get("question", ""),
            "option_a": options.get("A", ""),
            "option_b": options.get("B", ""),
            "option_c": options.get("C", ""),
            "option_d": options.get("D", ""),
            "correct_answer_key": correct_key,
            "correct_answer_text": options.get(correct_key, ""),
            "predicted_level": ev["predicted_level"],
            "classifier_confidence": ev["confidence"],
            "level_match": ev["level_match"],
            "quality_score": ev["quality_score"],
            "relevance_score": ev["relevance_score"],
            "overall_score": ev["overall_score"],
            "latency_sec": result.get("latency_sec"),
        })

    if rows:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_csv_headers())
            writer.writerows(rows)

    return {
        "csv_path": CSV_PATH,
        "rows_written": len(rows),
        "run_id": run_id,
    }
