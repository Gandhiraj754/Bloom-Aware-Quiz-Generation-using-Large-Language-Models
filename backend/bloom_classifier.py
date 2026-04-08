# ============================================================
#  bloom_classifier.py  —  Auto-verify question Bloom level
#
#  Two modes:
#  1. FAST (default): keyword heuristic — instant, no GPU needed
#  2. BERT (research): fine-tuned classifier on EduQG dataset
#     Activate by calling train_bert_classifier() once
# ============================================================

import re
from typing import Optional


def _tokenize(text: str) -> set[str]:
    """Simple lowercase tokenizer for lightweight lexical overlap checks."""
    return {t for t in re.findall(r"[a-zA-Z]{4,}", (text or "").lower())}


def score_pdf_relevance(question: dict, context: str) -> float:
    """
    0-1 relevance score for how grounded a question is in the provided PDF context.
    This is lightweight and deterministic so it can run on every request.
    """
    if not (context or "").strip():
        return 0.0

    options = question.get("options", {})
    correct_key = question.get("correct_answer")
    correct_text = options.get(correct_key, "")

    question_text = " ".join([
        question.get("question", ""),
        question.get("explanation", ""),
        question.get("bloom_justification", ""),
    ])

    context_tokens = _tokenize(context)
    question_tokens = _tokenize(question_text)
    answer_tokens = _tokenize(correct_text)

    if not context_tokens or not question_tokens:
        return 0.0

    evidence_overlap = len(question_tokens & context_tokens) / max(len(question_tokens), 1)
    answer_support = len(answer_tokens & context_tokens) / max(len(answer_tokens), 1) if answer_tokens else 0.0
    hallucination_penalty = 1.0 - evidence_overlap

    relevance = (0.5 * evidence_overlap) + (0.3 * answer_support) + (0.2 * (1.0 - hallucination_penalty))
    return round(max(0.0, min(relevance, 1.0)), 3)

# ── Keyword heuristic classifier (always available) ───────────

BLOOM_KEYWORDS = {
    1: {
        "strong": ["define","list","recall","name","identify","state","what is","who is","when did","where is","which","label"],
        "weak":   ["recognize","memorize","repeat","match"],
        "forbidden": ["compare","analyze","design","evaluate","create","why","how does","relationship"]
    },
    2: {
        "strong": ["explain","describe","summarize","classify","paraphrase","interpret","what does","what is the main","how would you describe","give an example"],
        "weak":   ["outline","illustrate","translate"],
        "forbidden": ["compare","design","evaluate","create","critique","justify"]
    },
    3: {
        "strong": ["apply","use","solve","demonstrate","calculate","show how","given","implement","execute","what would you do","use the concept"],
        "weak":   ["practice","carry out","perform"],
        "forbidden": ["compare","design","evaluate","critique","which is better"]
    },
    4: {
        "strong": ["compare","contrast","differentiate","analyze","examine","infer","what is the relationship","why does","break down","distinguish","what evidence","cause","effect"],
        "weak":   ["categorize","attribute","organize"],
        "forbidden": ["design","create","build","construct","propose","evaluate","best approach"]
    },
    5: {
        "strong": ["evaluate","judge","justify","critique","assess","defend","argue","which is best","most effective","strongest argument","validity","pros and cons","is it better"],
        "weak":   ["recommend","rate","prioritize"],
        "forbidden": ["design","create","build","construct","propose","define","list"]
    },
    6: {
        "strong": ["design","create","build","construct","propose","formulate","develop","plan","compose","generate","invent","what would you create","how would you design"],
        "weak":   ["produce","assemble","devise"],
        "forbidden": ["define","list","recall","what is","explain"]
    },
}

def classify_question_heuristic(question_text: str) -> dict:
    """
    Classify a question's Bloom level using keyword matching.
    Returns: {predicted_level, confidence, scores_per_level}
    """
    text   = question_text.lower()
    scores = {}

    for level, kw in BLOOM_KEYWORDS.items():
        score = 0.0
        for word in kw["strong"]:
            if word in text:
                score += 2.0
        for word in kw["weak"]:
            if word in text:
                score += 0.5
        for word in kw["forbidden"]:
            if word in text:
                score -= 1.5
        scores[level] = max(score, 0.0)

    total = sum(scores.values())
    if total == 0:
        probs = {l: 1/6 for l in range(1, 7)}
        confidence = 0.17
        predicted  = 1
    else:
        probs      = {l: round(s / total, 3) for l, s in scores.items()}
        predicted  = max(scores, key=scores.get)
        confidence = round(probs[predicted], 3)

    return {
        "predicted_level": predicted,
        "confidence":      confidence,
        "scores":          probs,
        "method":          "heuristic",
    }


def score_question_quality(question: dict) -> float:
    """
    0–1 quality score based on structural checks:
    - Has 4 options
    - Options are distinct enough
    - Has an explanation
    - Has a bloom_justification
    - Question length reasonable
    - Correct answer exists
    """
    score = 0.0

    options = question.get("options", {})
    if len(options) == 4:              score += 0.2
    if question.get("explanation"):    score += 0.2
    if question.get("bloom_justification"): score += 0.2

    q_text = question.get("question", "")
    if 20 <= len(q_text) <= 400:       score += 0.2

    if question.get("correct_answer") in options: score += 0.1

    vals = list(options.values())
    if len(set(vals)) == len(vals):    score += 0.1  # all options unique

    return round(score, 2)


def evaluate_question_item(question: dict, requested_level: int, context: str = "") -> dict:
    """Detailed per-question evaluation record used in APIs and CSV logging."""
    q_text = question.get("question", "")
    cls = classify_question_heuristic(q_text)
    quality = score_question_quality(question)
    relevance = score_pdf_relevance(question, context)
    is_match = cls["predicted_level"] == requested_level
    overall = round((0.4 * (1.0 if is_match else 0.0)) + (0.3 * quality) + (0.3 * relevance), 3)

    return {
        "question_id": question.get("id"),
        "question": q_text,
        "requested_level": requested_level,
        "predicted_level": cls["predicted_level"],
        "confidence": cls["confidence"],
        "level_match": is_match,
        "quality_score": quality,
        "relevance_score": relevance,
        "overall_score": overall,
    }


def evaluate_questions_detailed(result: dict, requested_level: Optional[int], context: str = "") -> list[dict]:
    """
    Evaluate each question in detail.
    If requested_level is None or 0, use each question's own bloom_level field when present.
    """
    rows = []
    for q in result.get("questions", []):
        level = requested_level if requested_level else q.get("bloom_level", result.get("bloom_level", 1))
        rows.append(evaluate_question_item(q, level, context=context))
    return rows


def evaluate_quiz_result(result: dict, requested_level: int, context: str = "") -> dict:
    """
    Full evaluation of a generated quiz.
    Returns classifier accuracy, quality scores, per-question breakdown.
    """
    questions = result.get("questions", [])
    if not questions:
        return {"classifier_accuracy": 0, "avg_question_quality": 0, "breakdown": []}

    breakdown = evaluate_questions_detailed(result, requested_level=requested_level, context=context)
    level_matches = sum(1 for b in breakdown if b["level_match"])
    quality_scores = [b["quality_score"] for b in breakdown]
    relevance_scores = [b["relevance_score"] for b in breakdown]

    classifier_accuracy   = round(level_matches / len(questions), 3)
    avg_quality           = round(sum(quality_scores) / len(quality_scores), 3)
    avg_relevance         = round(sum(relevance_scores) / len(relevance_scores), 3) if relevance_scores else 0.0

    return {
        "classifier_accuracy":   classifier_accuracy,
        "avg_question_quality":  avg_quality,
        "avg_pdf_relevance":     avg_relevance,
        "num_questions":         len(questions),
        "level_matches":         level_matches,
        "breakdown":             breakdown,
    }


# ── BERT classifier (optional, for research depth) ────────────

def is_bert_available() -> bool:
    try:
        import transformers
        import torch
        model_path = "bloom_bert_model"
        import os
        return os.path.exists(model_path)
    except ImportError:
        return False


def classify_with_bert(question_text: str) -> Optional[dict]:
    """
    Use fine-tuned BERT if available, otherwise return None.
    Train it with: python train_bert.py
    """
    if not is_bert_available():
        return None
    try:
        from transformers import pipeline
        clf = pipeline("text-classification", model="bloom_bert_model")
        result = clf(question_text)[0]
        level  = int(result["label"].replace("LABEL_", "")) + 1
        return {
            "predicted_level": level,
            "confidence":      round(result["score"], 3),
            "method":          "bert",
        }
    except Exception:
        return None
