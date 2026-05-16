
from validators.syllabus_validator import validate_question
from services.module_detector import detect_modules
from services.bloom_classifier import classify_bloom


# ── Retrieval confidence thresholds ────────────────────────────────────────────
# These values are intentionally conservative to minimise false positives.
THRESHOLD_STRONG  = 0.88   # > 0.88  → STRONG_MATCH
THRESHOLD_PARTIAL = 0.75   # 0.75–0.88 → PARTIAL_MATCH
THRESHOLD_WEAK    = 0.60   # 0.60–0.75 → WEAK_MATCH
                           # < 0.60  → NO_MATCH


def _classify_match_strength(similarity: float) -> str:
    if similarity > THRESHOLD_STRONG:
        return "STRONG_MATCH"
    elif similarity >= THRESHOLD_PARTIAL:
        return "PARTIAL_MATCH"
    elif similarity >= THRESHOLD_WEAK:
        return "WEAK_MATCH"
    else:
        return "NO_MATCH"


def _classify_match_type(similarity: float, syllabus_id_scoped: bool) -> str:
    """
    Determine the match_type for curriculum-driven reporting.

    DIRECT_SUBJECT_MATCH   — strong match inside the selected subject scope
    RELATED_CURRICULUM_MATCH — partial/weak match (may relate to other topics)
    OUT_OF_CURRICULUM      — insufficient evidence in any ingested content
    """
    if similarity >= THRESHOLD_PARTIAL and syllabus_id_scoped:
        return "DIRECT_SUBJECT_MATCH"
    elif similarity >= THRESHOLD_WEAK:
        return "RELATED_CURRICULUM_MATCH"
    else:
        return "OUT_OF_CURRICULUM"


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
      6. PCO mapping  [Feature 3B]
      7. Match type classification (DIRECT_SUBJECT / RELATED / OUT_OF_CURRICULUM)

    Returns a dict.  All existing keys are preserved; new keys are appended.
    """
    if syllabus_meta is None:
        syllabus_meta = {}

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
            if mapped_co and syllabus_id:
                mapped_pco = co_mapper.get_pco_for_co(syllabus_id, mapped_co)
        except Exception:
            mapped_co  = None
            mapped_pco = None

    # --------------------------------------------------------
    # Retrieval Confidence Gate — new spec thresholds
    # --------------------------------------------------------
    match_strength = _classify_match_strength(similarity)
    match_type     = _classify_match_type(similarity, syllabus_id_scoped=bool(syllabus_id))
    retrieval_status = "MATCH_FOUND" if match_strength != "NO_MATCH" else "NO_MATCH"

    # --------------------------------------------------------
    # Gatekeeper logic (threshold from caller, e.g. 0.2 default)
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
            # Enrichment keys
            "retrieval_status":  retrieval_status,
            "match_strength":    match_strength,
            "match_type":        match_type,
            "modules_detected":  modules_detected,
            "bloom_level":       bloom_result["bloom_level"],
            "difficulty":        bloom_result["difficulty"],
            "mapped_co":         mapped_co,
            "mapped_pco":        mapped_pco,
        }

    # LLM validation — NOT modified
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
        # Enrichment keys
        "retrieval_status":  retrieval_status,
        "match_strength":    match_strength,
        "match_type":        match_type,
        "modules_detected":  modules_detected,
        "bloom_level":       bloom_result["bloom_level"],
        "difficulty":        bloom_result["difficulty"],
        "mapped_co":         mapped_co,
        "mapped_pco":        mapped_pco,
    }
