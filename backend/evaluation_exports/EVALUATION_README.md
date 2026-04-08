# Bloom Quiz Evaluation Guide (Teacher Version)

## Purpose
This system evaluates AI-generated multiple-choice questions in three ways:
1. Bloom level alignment
2. Question quality
3. Relevance to the uploaded PDF content

It also saves every generated question and its evaluation into a CSV file for review.

## Where the data is saved
- CSV log file: `backend/evaluation_exports/generated_questions_log.csv`
- One row is added per generated question.
- Logging happens automatically when using:
  - `/api/generate`
  - `/api/generate/multi-level`
  - `/api/generate/compare`

## What is evaluated for each question
Each question gets these scores:

1. `predicted_level`
- Auto-detected Bloom level based on question wording.

### Bloom level meaning (for `predicted_level` and `requested_bloom_level`)
1. **Level 1 — Remember**
- Recall facts, terms, definitions, names, dates.
- Typical stems: "What is...", "Which of the following...", "Name...", "List..."

2. **Level 2 — Understand**
- Explain ideas, summarize, interpret meaning.
- Typical stems: "Which best explains...", "What does this mean...", "Summarize..."

3. **Level 3 — Apply**
- Use knowledge in a new situation or solve a problem.
- Typical stems: "Given this scenario...", "How would you use...", "Apply..."

4. **Level 4 — Analyze**
- Compare, differentiate, identify relationships/causes.
- Typical stems: "Compare...", "What is the relationship...", "Why does..."

5. **Level 5 — Evaluate**
- Judge and justify based on criteria/evidence.
- Typical stems: "Which is best and why...", "Assess...", "Critique..."

6. **Level 6 — Create**
- Design, propose, or produce something original.
- Typical stems: "Design a...", "Propose...", "Construct..."

### How to read `predicted_level`
- If `predicted_level = 1`, the classifier believes the question is **Remember** level.
- If `predicted_level = 6`, the classifier believes the question is **Create** level.
- Compare `predicted_level` with `requested_bloom_level` to check if the AI stayed at the intended cognitive depth.

2. `level_match`
- `true` if predicted level equals requested level.
- `false` if not.

3. `quality_score` (0 to 1)
- Checks structure and clarity:
  - Has 4 options
  - Has explanation
  - Has bloom justification
  - Reasonable question length
  - Correct answer key is valid
  - Options are not duplicates

4. `relevance_score` (0 to 1)
- Measures grounding to PDF context using lexical overlap:
  - overlap between question terms and PDF text
  - overlap between correct answer terms and PDF text
  - hallucination penalty when overlap is weak

5. `overall_score` (0 to 1)
- Combined indicator per question:

`overall_score = 0.4 * level_match_binary + 0.3 * quality_score + 0.3 * relevance_score`

Where `level_match_binary` is `1` for match and `0` for mismatch.

## CSV columns (important)
- `timestamp`: when the row was logged
- `endpoint`: generation route used
- `run_id`: unique id for a generation run
- `session_id`: linked quiz session id (if available)
- `topic`, `model`, `provider`
- `requested_bloom_level`, `predicted_level`, `classifier_confidence`
- `question_text`, options `A-D`, `correct_answer_key`, `correct_answer_text`
- `level_match`, `quality_score`, `relevance_score`, `overall_score`
- `latency_sec`

## How to explain results to students/parents
- High `level_match` means the AI followed the intended cognitive level.
- High `quality_score` means the question is structurally well-formed.
- High `relevance_score` means the question is more connected to the source PDF.
- Use `overall_score` as a summary, but always review low-scoring questions manually.
- Example: if a teacher requests Level 4 (Analyze) but `predicted_level` is 1 (Remember), the question is too basic and should be revised.

## Suggested teacher rubric
Use this quick interpretation for each question:
- `0.85 - 1.00`: Excellent
- `0.70 - 0.84`: Good
- `0.50 - 0.69`: Needs revision
- `< 0.50`: Not acceptable without edits

## Good practice for fair evaluation
1. Use the same PDF and topic across multiple models.
2. Generate at least 20 to 30 questions per Bloom level before comparing models.
3. Check both automated scores and teacher judgment.
4. Keep examples of accepted and rejected questions for moderation.

## Limitations (important for research transparency)
- Bloom detection is heuristic, not a full human cognitive assessment.
- Relevance score is lexical and may miss deep semantic similarity.
- Automated scores support, but do not replace, teacher review.

## Short summary for report writing
This project evaluates AI-generated quiz questions using Bloom alignment, structural quality, and PDF relevance. Each generated question is automatically scored and logged in CSV, enabling transparent auditing, model comparison, and teacher moderation.
