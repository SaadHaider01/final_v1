"""
services/bloom_classifier.py
------------------------------
Feature 2: Bloom's Taxonomy classification + difficulty mapping.

Uses a two-pass hybrid approach:
  Pass 1 — Action verb detection (fast, deterministic)
            Checks in descending cognitive order so higher-order verbs win.
  Pass 2 — WH-question pattern detection
            Handles "What is / What are / How does / Why / ..." style questions
            which are common in exams but lack explicit action verbs.

Returns:
    {
        "bloom_level": "Analyze",
        "difficulty":  "Medium"
    }

This module has NO side effects and does NOT affect syllabus validation logic.
"""

import re

# --------------------------------------------------
# Pass 1 — Action verb patterns
# --------------------------------------------------

BLOOM_VERB_MAP = {
    "Remember": [
        "define", "list", "state", "recall", "name", "identify",
        "label", "memorize", "recognize", "reproduce", "repeat",
    ],
    "Understand": [
        "explain", "describe", "summarize", "classify", "interpret",
        "paraphrase", "discuss", "outline", "illustrate", "review",
        "clarify", "translate",
    ],
    "Apply": [
        "implement", "use", "apply", "solve", "demonstrate",
        "execute", "operate", "compute", "calculate", "practice",
        "show", "produce",
    ],
    "Analyze": [
        "compare", "differentiate", "analyze", "analyse", "examine",
        "distinguish", "contrast", "investigate", "break down",
        "deconstruct", "test", "categorize",
    ],
    "Evaluate": [
        "justify", "assess", "evaluate", "judge", "critique",
        "argue", "defend", "recommend", "appraise", "rate",
        "select", "prioritize",
    ],
    "Create": [
        "design", "develop", "create", "construct", "formulate",
        "generate", "plan", "compose", "build", "invent",
        "propose", "devise",
    ],
}

# Maps Bloom level → difficulty tier
DIFFICULTY_MAP = {
    "Remember":   "Easy",
    "Understand": "Easy",
    "Apply":      "Medium",
    "Analyze":    "Medium",
    "Evaluate":   "Hard",
    "Create":     "Hard",
    "Unknown":    "Unknown",
}

# Pre-compile verb regexes
_VERB_COMPILED: dict = {}

def _get_verb_compiled():
    global _VERB_COMPILED
    if _VERB_COMPILED:
        return _VERB_COMPILED
    for level, verbs in BLOOM_VERB_MAP.items():
        patterns = [r"\b" + re.escape(v) + r"\b" for v in verbs]
        _VERB_COMPILED[level] = re.compile("|".join(patterns), re.IGNORECASE)
    return _VERB_COMPILED

# --------------------------------------------------
# Pass 2 — WH-question patterns
# --------------------------------------------------
# These cover questions like "What is X?", "What are the types of X?",
# "How does X work?", "Why is X important?", etc.
# Ordered from higher to lower cognitive level so that the first match wins.

_WH_PATTERNS = [
    # Evaluate / Analyze
    (re.compile(r"^\s*(why|why\s+is|why\s+are|why\s+do|why\s+does|why\s+should)\b", re.I), "Evaluate"),
    (re.compile(r"\b(advantage|disadvantage|benefit|drawback|limitation|trade.?off|pros?\s+and\s+cons?)\b", re.I), "Evaluate"),

    # Analyze
    (re.compile(r"\b(difference|differences|differ|distinguish|compare|contrast|similarities|vs\.?|versus)\b", re.I), "Analyze"),
    (re.compile(r"\b(how\s+does|how\s+do|how\s+is|how\s+are|how\s+can|how\s+to)\b", re.I), "Analyze"),

    # Understand
    (re.compile(r"\b(what\s+are\s+the\s+(different\s+)?(types?|kinds?|forms?|categories|components?|elements?|phases?|stages?|steps?|parts?))\b", re.I), "Understand"),
    (re.compile(r"\b(brief(ly)?|short\s+note|outline|overview|concept\s+of)\b", re.I), "Understand"),

    # Remember — "What is X", "What are X", "When", "Who", "Where", "Which"
    (re.compile(r"^\s*(what\s+is|what\s+are|what\s+was|what\s+were|what\s+do\s+you\s+mean)\b", re.I), "Remember"),
    (re.compile(r"^\s*(who|when|where|which)\b", re.I), "Remember"),
    (re.compile(r"\b(full\s+form|abbreviation|acronym|stand\s+for|meaning\s+of)\b", re.I), "Remember"),
]


# --------------------------------------------------
# Public API
# --------------------------------------------------

def classify_bloom(question: str) -> dict:
    """
    Classify a question into a Bloom's taxonomy level.

    Args:
        question: raw question string (any subject domain)

    Returns:
        dict with keys 'bloom_level' and 'difficulty'
    """
    q = question.strip()

    # ---------- Pass 1: action verb detection ----------
    compiled = _get_verb_compiled()
    ordered_levels = ["Create", "Evaluate", "Analyze", "Apply", "Understand", "Remember"]
    for level in ordered_levels:
        if compiled[level].search(q):
            return {"bloom_level": level, "difficulty": DIFFICULTY_MAP[level]}

    # ---------- Pass 2: WH-question pattern ----------
    for pattern, level in _WH_PATTERNS:
        if pattern.search(q):
            return {"bloom_level": level, "difficulty": DIFFICULTY_MAP[level]}

    # No match
    return {"bloom_level": "Unknown", "difficulty": "Unknown"}
