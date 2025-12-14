import re
import os
from typing import List, Dict
from llama_cpp import Llama

from config import LLM_MODEL_PATH, LLM_RUNTIME

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
You are a university syllabus validator.

Question:
{question}

Syllabus Content:
{syllabus_snippet}

Answer STRICTLY in this format:

DECISION: YES or NO
JUSTIFICATION: one short sentence
MODULE: module name or unknown

Rules:
- YES only if the syllabus supports answering this question.
- NO if it goes beyond syllabus scope.
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
            "llm_decision": "NO",
            "llm_justification": "Question is not sufficiently similar to syllabus content.",
            "llm_module": "unknown"
        }

    q_type = detect_question_type(question)
    core_terms = extract_core_terms(question)
    topic_present = topic_present_in_syllabus(core_terms, top_chunks)

    # 2️⃣ Definition questions
    if q_type == "definition":
        if topic_present:
            return {
                "llm_decision": "YES",
                "llm_justification": "The topic is explicitly listed in the syllabus.",
                "llm_module": top_chunks[0].get("module") or "unknown"
            }
        else:
            return {
                "llm_decision": "NO",
                "llm_justification": "The topic is not mentioned in the syllabus.",
                "llm_module": "unknown"
            }

    # 3️⃣ Unknown but grounded → allow
    if q_type == "unknown" and topic_present:
        return {
            "llm_decision": "YES",
            "llm_justification": "The question is grounded in syllabus topics.",
            "llm_module": top_chunks[0].get("module") or "unknown"
        }

    # 4️⃣ Application / analytical → LLM
    if q_type == "application":
        llm_result = llm_validate_application(question, top_chunks)
        return {
            "llm_decision": llm_result["decision"],
            "llm_justification": llm_result["justification"],
            "llm_module": llm_result["module"]
        }

    # 5️⃣ Fallback
    return {
        "llm_decision": "NO",
        "llm_justification": "Validator could not confidently ground the question in the syllabus.",
        "llm_module": "unknown"
    }
