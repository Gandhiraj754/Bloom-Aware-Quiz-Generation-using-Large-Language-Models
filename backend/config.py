
# ── Model names ──────────────────────────────────────────────
GROQ_MODELS = {
    "LLaMA 3.3 70B (Groq)"  : "llama-3.3-70b-versatile",
    "LLaMA 3.1 8B (Groq)"   : "llama-3.1-8b-instant",
    "Mixtral 8x7B (Groq)"   : "mixtral-8x7b-32768",
    "Gemma 2 9B (Groq)"     : "gemma2-9b-it",
}

GEMINI_MODELS = {
    "Gemini 2.0 Flash Lite"  : "gemini-2.0-flash-lite",
    "Gemini 1.5 Flash"       : "gemini-1.5-flash-latest",
    "Gemini 2.0 Flash"       : "gemini-2.0-flash",
}

OLLAMA_MODELS = {
    "DeepSeek V2 16B (Local)" : "deepseek-v2:16b",
    "LLaMA 3.2 (Local)"       : "llama3.2:latest",
    "Phi-3 (Local)"           : "phi3:latest",
}

OPENROUTER_MODELS = {
    "LLaMA 3.3 70B (OpenRouter)"  : "meta-llama/llama-3.3-70b-instruct:free",
    "LLaMA 3.2 3B (OpenRouter)"   : "meta-llama/llama-3.2-3b-instruct:free",
    "Gemma 3 27B (OpenRouter)"    : "google/gemma-3-27b-it:free",
    "Gemma 3 12B (OpenRouter)"    : "google/gemma-3-12b-it:free",
    "Mistral Small (OpenRouter)"  : "mistralai/mistral-small-3.1-24b-instruct:free",
    "Qwen3 4B (OpenRouter)"       : "qwen/qwen3-4b:free",
    "GPT OSS 120B (OpenRouter)"   : "openai/gpt-oss-120b:free",
}

# ── Bloom level metadata ─────────────────────────────────────
BLOOM_LEVELS = {
    1: {
        "name"      : "Remember",
        "color"     : "#B4B2A9",
        "verbs"     : ["define", "list", "recall", "identify", "name", "state"],
        "description": "Recall facts and basic concepts",
    },
    2: {
        "name"      : "Understand",
        "color"     : "#378ADD",
        "verbs"     : ["explain", "summarize", "classify", "describe", "paraphrase"],
        "description": "Explain ideas or concepts in own words",
    },
    3: {
        "name"      : "Apply",
        "color"     : "#1D9E75",
        "verbs"     : ["solve", "use", "demonstrate", "execute", "implement"],
        "description": "Use information in new situations",
    },
    4: {
        "name"      : "Analyze",
        "color"     : "#EF9F27",
        "verbs"     : ["compare", "differentiate", "examine", "infer", "break down"],
        "description": "Draw connections and examine components",
    },
    5: {
        "name"      : "Evaluate",
        "color"     : "#D85A30",
        "verbs"     : ["judge", "critique", "justify", "assess", "defend", "argue"],
        "description": "Justify a decision or course of action",
    },
    6: {
        "name"      : "Create",
        "color"     : "#7F77DD",
        "verbs"     : ["design", "build", "compose", "plan", "formulate", "construct"],
        "description": "Produce new or original work",
    },
}

# ── App settings ─────────────────────────────────────────────
APP_TITLE      = "Bloom-Aware Quiz Generator"
MAX_QUESTIONS  = 10
DEFAULT_QUESTIONS = 3
OLLAMA_BASE_URL   = "http://localhost:11434"
