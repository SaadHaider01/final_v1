
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
    syllabus_meta: dict = None,
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
    # Feature 3: Semantic Domain Checking (False Positive Handling)
    # --------------------------------------------------------
    if syllabus_meta is None:
        syllabus_meta = {}
    
    subject_name = syllabus_meta.get("subject_name", "").lower()
    q_lower = question.lower()
    
    out_of_domain_keywords = [
        "blockchain", "kubernetes", "neural network", "cryptocurrency", 
        "phishing", "machine learning", "deep learning", "docker"
    ]
    
    for keyword in out_of_domain_keywords:
        # If question has the keyword, but it's not in the subject name
        if keyword in q_lower and keyword not in subject_name:
            # We assume it's a domain mismatch and penalize the similarity
            similarity -= 0.20
            break

    # --------------------------------------------------------
    # Feature 2: Retrieval Confidence Gate
    # --------------------------------------------------------
    if similarity > 0.75:
        match_strength = "STRONG_MATCH"
    elif similarity >= 0.55:
        match_strength = "PARTIAL_MATCH"
    elif similarity >= 0.40:
        match_strength = "WEAK_MATCH"
    else:
        match_strength = "NO_MATCH"
        
    retrieval_status = "MATCH_FOUND" if match_strength != "NO_MATCH" else "NO_MATCH"

    # --------------------------------------------------------
    # Existing gatekeeper logic
    # --------------------------------------------------------
    gatekeeper_passed = similarity >= threshold

    if not gatekeeper_passed or retrieval_status == "NO_MATCH":
        return {
            # Existing keys
            "is_in_syllabus":    False,
            "gatekeeper_passed": False,
            "reason":            "Low semantic similarity to syllabus.",
            "llm":               None,
            "top_chunks":        [] if retrieval_status == "NO_MATCH" else top_chunks,
            # New keys
            "retrieval_status":  retrieval_status,
            "match_strength":    match_strength,
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
        "top_chunks":        top_chunks,
        # New keys
        "retrieval_status":  retrieval_status,
        "match_strength":    match_strength,
        "modules_detected":  modules_detected,
        "bloom_level":       bloom_result["bloom_level"],
        "difficulty":        bloom_result["difficulty"],
        "mapped_co":         mapped_co,
        "mapped_pco":        mapped_pco,
    }
