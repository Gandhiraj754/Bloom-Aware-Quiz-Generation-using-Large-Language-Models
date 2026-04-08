# ============================================================
#  prompt_engine.py  —  Bloom-aware prompt templates
#  One template per level, forces the LLM to stay at that
#  cognitive depth. JSON output for easy parsing.
# ============================================================

from config import BLOOM_LEVELS

SYSTEM_PROMPT = """You are an expert educational assessment designer trained in 
Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001).
Your ONLY job is to generate multiple-choice questions at a SPECIFIC Bloom's level.
You must output ONLY valid JSON — no preamble, no explanation, no markdown fences."""


LEVEL_INSTRUCTIONS = {
    1: """
BLOOM'S LEVEL 1 — REMEMBER
The student must RECALL or RECOGNIZE a fact directly from memory.
Cognitive action: retrieve relevant knowledge from long-term memory.

REQUIRED question stems: "What is...", "Which of the following defines...", 
"Name the...", "List the...", "Who was...", "When did..."

FORBIDDEN: questions requiring explanation, application, or reasoning.
The answer must be a direct fact — no computation, no judgment.""",

    2: """
BLOOM'S LEVEL 2 — UNDERSTAND
The student must INTERPRET or EXPLAIN a concept in their own words.
Cognitive action: construct meaning from instructional messages.

REQUIRED question stems: "What does X mean?", "Which best explains...", 
"In your own words...", "How would you describe...", "What is the main idea of..."

FORBIDDEN: questions that only recall facts (L1) or require applying knowledge (L3).
The student must demonstrate they understand — not just remember.""",

    3: """
BLOOM'S LEVEL 3 — APPLY
The student must USE knowledge to solve a problem or complete a task in a new situation.
Cognitive action: execute or implement a procedure.

REQUIRED question stems: "How would you solve...", "Which procedure would you use to...",
"Apply the concept of X to...", "Given the following scenario..., what would you do?",
"Calculate / Demonstrate / Use X to..."

FORBIDDEN: questions that only ask for definitions (L1/L2) or analysis (L4).
There must be a concrete scenario or problem to solve.""",

    4: """
BLOOM'S LEVEL 4 — ANALYZE
The student must BREAK DOWN information and identify relationships, patterns, or causes.
Cognitive action: differentiate, organize, attribute components.

REQUIRED question stems: "Compare X and Y...", "What is the relationship between...",
"Why does X cause Y?", "Which evidence supports...", "What would happen if...",
"Distinguish between...", "What is the underlying reason for..."

FORBIDDEN: questions with a single factual answer. The student must reason about structure,
causes, or relationships — not just recall or apply.""",

    5: """
BLOOM'S LEVEL 5 — EVALUATE
The student must MAKE A JUDGMENT and JUSTIFY it based on criteria or evidence.
Cognitive action: check, critique, judge, defend a position.

REQUIRED question stems: "Which approach is most effective and why?", 
"Critique the following argument...", "Defend or refute the claim that...",
"What is the strongest argument for...", "Assess the validity of...",
"Which solution is best given the constraints..."

FORBIDDEN: questions with objectively correct answers. There must be a position to defend,
a trade-off to weigh, or a judgment to justify. Think: debate, not quiz.""",

    6: """
BLOOM'S LEVEL 6 — CREATE
The student must SYNTHESIZE ideas to produce something NEW — a plan, design, or proposal.
Cognitive action: generate, plan, produce original work.

REQUIRED question stems: "Design a system that...", "Propose a solution to...",
"Formulate a plan for...", "What would you create to...", "Construct a framework for...",
"How would you design an experiment to..."

FORBIDDEN: questions that only recall, apply, or evaluate existing ideas.
The student must demonstrate synthesis — combining elements into something that didn't exist before.
The correct answer will describe a novel plan, design, or proposal.""",
}


def build_prompt(topic: str, context: str, bloom_level: int, num_questions: int) -> str:
    """
    Build a complete Bloom-aware prompt for a given topic and level.
    Returns the user-turn message; SYSTEM_PROMPT is sent separately.
    """
    level_info  = BLOOM_LEVELS[bloom_level]
    level_instr = LEVEL_INSTRUCTIONS[bloom_level]
    verbs       = ", ".join(level_info["verbs"])

    prompt = f"""
{level_instr}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generate exactly {num_questions} multiple-choice question(s) about:
TOPIC: {topic}

{"REFERENCE CONTENT:" + chr(10) + context[:3000] if context.strip() else "Use your knowledge about this topic."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Cognitive level: ONLY Bloom's Level {bloom_level} ({level_info["name"].upper()})
• Use action verbs: {verbs}
• Each question: 1 correct answer + 3 plausible wrong answers
• Wrong answers must be believable, not obviously wrong
• Think step by step about WHY this is a Level {bloom_level} question before writing it

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — valid JSON only, exactly this structure:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "bloom_level": {bloom_level},
  "bloom_level_name": "{level_info["name"]}",
  "topic": "{topic}",
  "questions": [
    {{
      "id": 1,
      "question": "Your question here?",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "correct_answer": "A",
      "explanation": "Why this is correct and why others are wrong.",
      "bloom_justification": "This is Level {bloom_level} because it requires the student to [specific cognitive action]."
    }}
  ]
}}
"""
    return prompt.strip()
