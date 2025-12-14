
from validators.syllabus_validator import validate_question

def analyze_question(
    question: str,
    similarity: float,
    threshold: float,
    top_chunks: list,
):
    """
    Orchestrates gatekeeper + LLM grounding
    """

    gatekeeper_passed = similarity >= threshold

    if not gatekeeper_passed:
        return {
            "is_in_syllabus": False,
            "gatekeeper_passed": False,
            "reason": "Low semantic similarity to syllabus.",
            "llm": None,
        }

    llm_res = validate_question(
    question=question,
    top_chunks=top_chunks,
    similarity=similarity,
    threshold=threshold
)


    is_in = llm_res["llm_decision"] == "YES"

    return {
        "is_in_syllabus": is_in,
        "gatekeeper_passed": True,
        "reason": llm_res["llm_justification"],
        "llm": llm_res,
    }
