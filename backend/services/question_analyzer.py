
from validators.syllabus_validator import validate_question
from services.module_detector import detect_modules
from services.bloom_classifier import classify_bloom


def analyze_question(
    question: str,
    similarity: float,
    threshold: float,
    top_chunks: list,
    co_mapper=None,        # optional CoMapper instance
    syllabus_id: str = None,
):
    """
    Orchestrates:
      1. Gatekeeper (cosine similarity threshold)
      2. LLM grounding (existing, unchanged)
      3. Multi-module detection  [Feature 1]
      4. Bloom taxonomy + difficulty  [Feature 2]
      5. CO mapping  [Feature 3]
      6. PCO mapping  [Feature 3B — NEW]

    Returns a dict.  All existing keys are preserved; new keys are appended.
    """

    # --------------------------------------------------------
    # Feature 1: Multi-module detection (always runs — fast)
    # --------------------------------------------------------
    modules_detected = detect_modules(top_chunks)

    # --------------------------------------------------------
    # Feature 2: Bloom + difficulty (always runs — pure regex)
    # --------------------------------------------------------
    bloom_result = classify_bloom(question)

    # --------------------------------------------------------
    # Feature 3: CO mapping (only if CoMapper provided)
    # --------------------------------------------------------
    mapped_co  = None
    mapped_pco = None
    if co_mapper is not None:
        try:
            mapped_co = co_mapper.map_question_to_co(question, syllabus_id)
            # Feature 3B: PCO lookup (dict — no embedding)
            if mapped_co and syllabus_id:
                mapped_pco = co_mapper.get_pco_for_co(syllabus_id, mapped_co)
        except Exception:
            mapped_co  = None
            mapped_pco = None

    # --------------------------------------------------------
    # Existing gatekeeper logic — NOT modified
    # --------------------------------------------------------
    gatekeeper_passed = similarity >= threshold

    if not gatekeeper_passed:
        return {
            # Existing keys
            "is_in_syllabus":    False,
            "gatekeeper_passed": False,
            "reason":            "Low semantic similarity to syllabus.",
            "llm":               None,
            # New keys
            "modules_detected":  modules_detected,
            "bloom_level":       bloom_result["bloom_level"],
            "difficulty":        bloom_result["difficulty"],
            "mapped_co":         mapped_co,
            "mapped_pco":        mapped_pco,
        }

    # Existing LLM validation — NOT modified
    llm_res = validate_question(
        question=question,
        top_chunks=top_chunks,
        similarity=similarity,
        threshold=threshold,
    )

    is_in = llm_res["llm_decision"] == "YES"

    return {
        # Existing keys
        "is_in_syllabus":    is_in,
        "gatekeeper_passed": True,
        "reason":            llm_res["llm_justification"],
        "llm":               llm_res,
        # New keys
        "modules_detected":  modules_detected,
        "bloom_level":       bloom_result["bloom_level"],
        "difficulty":        bloom_result["difficulty"],
        "mapped_co":         mapped_co,
        "mapped_pco":        mapped_pco,
    }
