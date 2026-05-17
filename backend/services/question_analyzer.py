
from validators.syllabus_validator import validate_question
from services.module_detector import detect_modules
from services.bloom_classifier import classify_bloom


# ── Retrieval confidence thresholds ────────────────────────────────────────────
# Tightened to reduce false positives from metadata-polluted embeddings.
THRESHOLD_STRONG  = 0.90   # > 0.90  → STRONG_MATCH   (near-certain content match)
THRESHOLD_PARTIAL = 0.82   # 0.82–0.90 → PARTIAL_MATCH (clear topic overlap)
THRESHOLD_WEAK    = 0.72   # 0.72–0.82 → WEAK_MATCH    (loose semantic relation)
                           # < 0.72  → NO_MATCH        (discard — too low to trust)


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
    """
    # If we are searching within a specific syllabus and have at least a weak semantic link,
    # the retrieved chunks BELONG to this subject. It is a direct match, even if conceptually expanded.
    if similarity >= THRESHOLD_WEAK and syllabus_id_scoped:
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
    # Retrieval Confidence Gate — strict thresholds
    # --------------------------------------------------------
    match_strength   = _classify_match_strength(similarity)
    match_type       = _classify_match_type(similarity, syllabus_id_scoped=bool(syllabus_id))
    is_no_match      = match_strength == "NO_MATCH"
    retrieval_status = "NO_MATCH" if is_no_match else "MATCH_FOUND"

    # --------------------------------------------------------
    # Gatekeeper logic (user-supplied threshold, default 0.80)
    # --------------------------------------------------------
    gatekeeper_passed = (not is_no_match) and (similarity >= threshold)

    # STEP 7: Hard NO_MATCH behavior — never leak weak chunks to the frontend
    if is_no_match or not gatekeeper_passed:
        return {
            # Existing keys
            "is_in_syllabus":    False,
            "gatekeeper_passed": False,
            "reason":            "Similarity below threshold — no valid syllabus content found.",
            "llm":               None,
            "top_chunks":        [],       # Always empty on NO_MATCH
            # Enrichment keys
            "retrieval_status":  retrieval_status,
            "match_strength":    match_strength,
            "match_type":        "OUT_OF_CURRICULUM",
            "modules_detected":  modules_detected,
            "bloom_level":       bloom_result["bloom_level"],
            "difficulty":        bloom_result["difficulty"],
            "mapped_co":         mapped_co,
            "mapped_pco":        mapped_pco,
            # NEW Grounding keys
            "curriculum_relevance": False,
            "strict_syllabus_match": False,
            "rejection_reason": "Similarity below threshold.",
        }

    # LLM validation — NOW INCLUDES STRICT GROUNDING
    llm_res = validate_question(
        question=question,
        top_chunks=top_chunks,
        similarity=similarity,
        threshold=threshold,
    )

    is_in = llm_res.get("is_in_syllabus", False)

    # --- FINAL FIX 2: MATCH TYPE CONSISTENCY ---
    if not is_in:
        match_type = "OUT_OF_CURRICULUM"

    # --- FINAL FIX 3: MATCH STRENGTH TUNING ---
    # Retrieve highest concept boost and semantic score from top_chunks
    concept_boost = top_chunks[0].get("concept_boost", 0.0) if top_chunks else 0.0
    semantic_score = top_chunks[0].get("semantic_score", 0.0) if top_chunks else 0.0
    
    if semantic_score >= 0.80 and concept_boost > 0 and bool(syllabus_id):
        # Prevent analytical questions from being downgraded to WEAK_MATCH
        if match_strength in ["NO_MATCH", "WEAK_MATCH"]:
            match_strength = "PARTIAL_MATCH"
            
    # --- FINAL FIX 4: MODULE DETECTION CLEANUP ---
    # Return ONLY the top 2 strongest modules to prevent UI bloat
    modules_detected = modules_detected[:2]
            
    # --- FINAL FIX 5: NO EMPTY MATCH FOUND STATES ---
    if not top_chunks:
        retrieval_status = "NO_MATCH"

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
        # NEW Grounding keys
        "curriculum_relevance":  llm_res.get("curriculum_relevance", True),
        "strict_syllabus_match": llm_res.get("strict_syllabus_match", False),
        "rejection_reason":      llm_res.get("rejection_reason", ""),
    }
