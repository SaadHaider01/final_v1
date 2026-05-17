import re
import os
from typing import List, Dict
from llama_cpp import Llama

from config import LLM_MODEL_PATH, LLM_RUNTIME
from services.grounding_validator import is_explicitly_grounded

# --------------------------------------------------
# Model loading (lazy singleton)
# --------------------------------------------------

_LLM = None

def get_llm():
    global _LLM

    if _LLM is not None:
        return _LLM

    if not LLM_MODEL_PATH:
        raise RuntimeError("LLM_MODEL_PATH is not set in config.py")

    if not os.path.exists(LLM_MODEL_PATH):
        raise RuntimeError(f"LLM model file not found: {LLM_MODEL_PATH}")

    print(f"[LLM] Loading model from: {LLM_MODEL_PATH}")

    _LLM = Llama(
        model_path=LLM_MODEL_PATH,
        n_ctx=LLM_RUNTIME.get("n_ctx", 2048),
        n_threads=LLM_RUNTIME.get("n_threads", 4),
        n_gpu_layers=LLM_RUNTIME.get("n_gpu_layers", 0), # Added for GPU offloading
        temperature=LLM_RUNTIME.get("temperature", 0.0),
        verbose=True,
    )

    return _LLM

# --------------------------------------------------
# Question understanding helpers
# --------------------------------------------------

def detect_question_type(question: str) -> str:
    q = question.lower()

    application_markers = [
        "case study", "scenario", "analyze", "how would you",
        "design", "implement", "evaluate", "justify", "compare"
    ]

    definition_markers = [
        "what is", "define", "explain", "describe",
        "short note", "meaning of", "overview of"
    ]

    if any(p in q for p in application_markers):
        return "application"

    if any(p in q for p in definition_markers):
        return "definition"

    return "unknown"

def extract_core_terms(question: str) -> List[str]:
    stopwords = {
        "what", "is", "the", "of", "and", "in", "to",
        "explain", "define", "describe", "how"
    }

    tokens = re.findall(r"[a-zA-Z]+", question.lower())
    return [t for t in tokens if t not in stopwords][:4]

def topic_present_in_syllabus(core_terms: List[str], chunks: List[Dict]) -> bool:
    syllabus_text = " ".join(c["text"].lower() for c in chunks)
    return any(term in syllabus_text for term in core_terms)

# --------------------------------------------------
# LLM validation (ONLY for application questions)
# --------------------------------------------------

def llm_validate_application(question: str, chunks: List[Dict]) -> Dict:
    llm = get_llm()

    syllabus_snippet = "\n".join(
        f"- {c['text'][:200]}" for c in chunks[:3]
    )

    prompt = f"""
You are a strict university syllabus validator.

Question:
{question}

Syllabus Content:
{syllabus_snippet}

Answer STRICTLY in this format:

DECISION: YES or NO
JUSTIFICATION: one short sentence
MODULE: module name or unknown

Rules:
- YES only if the syllabus EXPLICITLY supports the application domain AND provides sufficient technical depth to answer the question.
- NO if it introduces an external application domain not present in the syllabus, even if the underlying concepts are related.
- DO NOT infer modern applications from generic concepts.
"""

    response = llm(
        prompt,
        max_tokens=120,
        stop=["</s>"]
    )

    text = response["choices"][0]["text"]

    decision = "NO"
    justification = "LLM could not validate."
    module = "unknown"

    for line in text.splitlines():
        if line.upper().startswith("DECISION:"):
            decision = line.split(":", 1)[1].strip()
        elif line.upper().startswith("JUSTIFICATION:"):
            justification = line.split(":", 1)[1].strip()
        elif line.upper().startswith("MODULE:"):
            module = line.split(":", 1)[1].strip()

    return {
        "decision": decision,
        "justification": justification,
        "module": module
    }

# --------------------------------------------------
# MAIN VALIDATOR ENTRY POINT
# --------------------------------------------------

def validate_question(
    question: str,
    top_chunks: List[Dict],
    similarity: float,
    threshold: float = 0.2
) -> Dict:

    # 1️⃣ Similarity gate
    if similarity < threshold:
        return {
            "curriculum_relevance": False,
            "strict_syllabus_match": False,
            "is_in_syllabus": False,
            "rejection_reason": "Question is not sufficiently similar to syllabus content.",
            "llm_decision": "NO",
            "llm_justification": "Question is not sufficiently similar to syllabus content.",
            "llm_module": "unknown"
        }

    # At this point, it passes the semantic threshold -> it has curriculum relevance
    curriculum_relevance = True
    
    # 2️⃣ Strict Grounding Gate (Domain Intrusion Detection)
    q_type = detect_question_type(question)
    is_grounded, rejection_reason = is_explicitly_grounded(question, top_chunks, q_type)
    if not is_grounded:
        return {
            "curriculum_relevance": curriculum_relevance,
            "strict_syllabus_match": False,
            "is_in_syllabus": False,
            "rejection_reason": rejection_reason,
            "llm_decision": "NO",
            "llm_justification": rejection_reason,
            "llm_module": "unknown"
        }

    # Helper function to format return
    def _make_result(strict_match: bool, justification: str, module: str) -> Dict:
        return {
            "curriculum_relevance": curriculum_relevance,
            "strict_syllabus_match": strict_match,
            "is_in_syllabus": strict_match,
            "rejection_reason": justification if not strict_match else "",
            "llm_decision": "YES" if strict_match else "NO",
            "llm_justification": justification,
            "llm_module": module
        }

    core_terms = extract_core_terms(question)
    topic_present = topic_present_in_syllabus(core_terms, top_chunks)

    # 3️⃣ Definition questions
    if q_type == "definition":
        if topic_present:
            return _make_result(True, "The topic is explicitly listed in the syllabus.", top_chunks[0].get("module") or "unknown")
        else:
            return _make_result(False, "The topic is not explicitly mentioned in the syllabus.", "unknown")

    # 4️⃣ Unknown but grounded → allow
    if q_type == "unknown" and topic_present:
        return _make_result(True, "The question is grounded in syllabus topics.", top_chunks[0].get("module") or "unknown")

    # 5️⃣ Application / analytical → LLM
    if q_type == "application":
        llm_result = llm_validate_application(question, top_chunks)
        strict_match = llm_result["decision"] == "YES"
        return _make_result(strict_match, llm_result["justification"], llm_result["module"])

    # 6️⃣ Fallback
    return _make_result(False, "Validator could not confidently ground the question in the syllabus.", "unknown")
