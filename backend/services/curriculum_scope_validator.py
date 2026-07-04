"""
services/curriculum_scope_validator.py
---------------------------------------
Curriculum Scope Validator — deterministic pre-LLM gate.

During ingestion:
    Extracts high-quality technical concepts from each syllabus using
    spaCy noun chunks, acronyms, and capitalized entities.
    Generic course terms are filtered out, and the resulting specific
    concepts are persisted to ``data/scope_concepts.json``.

During question analysis:
    Computes a Concept Overlap Score using word-level semantic matching
    with a strict cosine threshold (0.86) to filter out weak stylistic
    associations, enhanced by a fast morphological heuristic (prefix/substring)
    to handle plural/singular and structural variants. If the score falls
    below a minimum threshold (0.24), the question is rejected as
    OUT_OF_CURRICULUM immediately.

Design principles:
  - Curriculum-agnostic  (no hardcoded subject dictionaries)
  - Stateless reads      (pure function for validate_scope)
  - Zero new dependencies (spaCy + sklearn already installed)
  - Silent pass-through  (if no concepts stored, gate is skipped)
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Storage path & Configuration
# ---------------------------------------------------------------------------

_DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "data")
_CONCEPTS_FILE = os.path.join(_DATA_DIR, "scope_concepts.json")

# In-memory caches
_concept_cache:       Dict[str, List[str]] = {}  # syllabus_id → concept list
_embedding_cache:     Dict[str, Any]       = {}  # syllabus_id → list of word embeddings
_syllabus_word_cache: Dict[str, List[str]] = {}  # syllabus_id → list of distinct words

# Query structures, auxiliary verbs, and generic course words to ignore
GENERIC_WORDS = {
    "what", "is", "are", "was", "were", "can", "could", "should", "would", "will", "shall",
    "does", "do", "did", "has", "have", "had", "define", "explain", "describe", "analyze",
    "compare", "role", "purpose", "difference", "between", "how", "why", "the", "and", "for",
    "with", "about", "various", "concept", "concepts", "working", "principle", "principles",
    "importance", "advantages", "limitations", "disadvantages", "portal", "university",
    "systems", "system", "scenario", "case", "design", "implement", "evaluate", "justify",
    "meaning", "question", "differentiate", "contrast", "methods", "method", "approach",
    "approaches", "techniques", "technique", "analysis", "role", "roles", "preventing",
    "unauthorized", "access", "prevent", "based", "using", "used", "implementation",
    "benefits", "drawbacks", "features", "feature", "applications", "application",
    "mechanisms", "mechanism", "authorities", "authority", "organizational", "introduction",
    "overview", "basics", "basic", "need", "module", "chapter", "unit", "study", "course",
    "applicable", "required", "syllabus", "topics", "together", "not required", "not", "required"
}

# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_store() -> Dict[str, List[str]]:
    if os.path.exists(_CONCEPTS_FILE):
        try:
            with open(_CONCEPTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_store(store: Dict[str, List[str]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_CONCEPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


# ---------------------------------------------------------------------------
# Concept extraction (ingestion time)
# ---------------------------------------------------------------------------

def extract_syllabus_concepts(text: str, top_n: int = 150) -> List[str]:
    """
    Extract the top technical concepts from syllabus text.

    Args:
        text:  Full syllabus text (from all chunks).
        top_n: Maximum number of concepts to keep.

    Returns:
        Deduplicated list of concept strings (lowercase).
    """
    try:
        return _extract_with_spacy(text, top_n)
    except Exception as e:
        print(f"[ScopeValidator] Falling back to frequency extraction: {e}")
        return _extract_by_frequency(text, top_n)


def _extract_with_spacy(text: str, top_n: int) -> List[str]:
    """spaCy noun chunks + entities with generic word filters."""
    import spacy
    
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text[:100_000])           # spaCy limit guard

    candidates: set = set()

    # 1. Noun chunks
    for chunk in doc.noun_chunks:
        tokens = [t for t in chunk if t.pos_ not in ("DET", "PRON", "PUNCT")]
        phrase = " ".join(t.text for t in tokens).strip().lower()
        phrase = re.sub(r"\s+", " ", phrase)
        
        # Filter out generic words completely or from start/end
        if not phrase or phrase in GENERIC_WORDS:
            continue
            
        words = phrase.split()
        words = [w for w in words if w not in GENERIC_WORDS]
        if words and len(" ".join(words)) > 2:
            candidates.add(" ".join(words))

    # 2. Capitalised phrases  e.g. "Hash Function", "RSA Algorithm"
    for cap in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text):
        phrase = cap.lower().strip()
        if phrase not in GENERIC_WORDS and len(phrase) > 2:
            candidates.add(phrase)

    # 3. Acronyms  e.g. RSA, AES, DES, SSL
    for acr in re.findall(r"\b[A-Z]{2,}\b", text):
        candidates.add(acr.lower())

    if not candidates:
        return []

    # Sort candidates by length (longer = more specific technical terms)
    ranked = sorted(list(candidates), key=len, reverse=True)
    return ranked[:top_n]


def _extract_by_frequency(text: str, top_n: int) -> List[str]:
    """Pure-Python frequency fallback — no external dependencies."""
    from collections import Counter

    tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    tokens = [t for t in tokens if t not in GENERIC_WORDS]
    counts = Counter(tokens)
    return [term for term, _ in counts.most_common(top_n)]


# ---------------------------------------------------------------------------
# Storage API
# ---------------------------------------------------------------------------

def store_scope_concepts(syllabus_id: str, concepts: List[str]) -> None:
    """Persist extracted concepts for a syllabus and update the in-memory cache."""
    store = _load_store()
    store[syllabus_id] = concepts
    _save_store(store)
    _concept_cache[syllabus_id] = concepts
    
    # Invalidate caches
    _embedding_cache.pop(syllabus_id, None)
    _syllabus_word_cache.pop(syllabus_id, None)
    print(f"[ScopeValidator] Stored {len(concepts)} concepts for '{syllabus_id}'")


def load_scope_concepts(syllabus_id: str) -> List[str]:
    """Load concepts for a syllabus from cache or disk."""
    if syllabus_id in _concept_cache:
        return _concept_cache[syllabus_id]
    store = _load_store()
    concepts = store.get(syllabus_id, [])
    _concept_cache[syllabus_id] = concepts
    return concepts


def delete_scope_concepts(syllabus_id: str) -> None:
    """Remove stored concepts for a deleted syllabus."""
    store = _load_store()
    if syllabus_id in store:
        del store[syllabus_id]
        _save_store(store)
    _concept_cache.pop(syllabus_id, None)
    _embedding_cache.pop(syllabus_id, None)
    _syllabus_word_cache.pop(syllabus_id, None)


def clear_all_scope_concepts() -> None:
    """Remove ALL stored concepts (used by /purge_all)."""
    _concept_cache.clear()
    _embedding_cache.clear()
    _syllabus_word_cache.clear()
    if os.path.exists(_CONCEPTS_FILE):
        os.remove(_CONCEPTS_FILE)


# ---------------------------------------------------------------------------
# Semantic overlap computation (query time)
# ---------------------------------------------------------------------------

def _cosine_similarity(a, b) -> float:
    """Cosine similarity between two 1-D numpy-compatible arrays."""
    import numpy as np

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _get_syllabus_words_and_embeddings(syllabus_id: str, embed_fn) -> Optional[tuple[List[str], Any]]:
    """
    Return and cache the token list and corresponding SBERT embeddings
    for all distinct words in the syllabus concepts.
    """
    if syllabus_id in _syllabus_word_cache and syllabus_id in _embedding_cache:
        return _syllabus_word_cache[syllabus_id], _embedding_cache[syllabus_id]

    concepts = load_scope_concepts(syllabus_id)
    if not concepts:
        return None

    # Deconstruct concepts into distinct words
    syllabus_words = set()
    for c in concepts:
        for w in re.findall(r"\b[a-zA-Z]{3,}\b", c.lower()):
            syllabus_words.add(w)
    
    syllabus_words_list = list(syllabus_words)
    if not syllabus_words_list:
        return None

    try:
        embs = embed_fn(syllabus_words_list, task="passage")
    except TypeError:
        embs = embed_fn(syllabus_words_list)

    _syllabus_word_cache[syllabus_id] = syllabus_words_list
    _embedding_cache[syllabus_id]     = embs
    return syllabus_words_list, embs


def _is_morphological_match(w1: str, w2: str) -> bool:
    """
    Fast, curriculum-agnostic prefix/substring matching to handle plural/singular
    and basic morphological derivations without heavy lemmatizers.
    """
    w1_len, w2_len = len(w1), len(w2)
    if w1_len < 4 or w2_len < 4:
        return False
    # Substring matching (e.g. "cipher" in "ciphertext")
    if w1 in w2 and w1_len >= 5:
        return True
    if w2 in w1 and w2_len >= 5:
        return True
    # Prefix matching (e.g. "cryptography" vs "cryptanalysis")
    min_len = min(w1_len, w2_len)
    if min_len >= 5:
        if w1[:5] == w2[:5]:
            return True
    return False


def compute_concept_overlap(question: str, syllabus_id: str, embed_fn, semantic_cutoff: float = 0.86) -> float:
    """
    Compute semantic concept overlap using token-level max-similarity with a threshold cutoff.

    Method:
        1. Tokenize question to extract specific technical content words (ignore GENERIC_WORDS).
        2. For each query word:
           - If it matches a syllabus word exactly -> score = 1.0.
           - If it matches morphologically (prefix/substring) -> score = 1.0.
           - Else -> find the max SBERT cosine similarity to any syllabus word.
           - If similarity >= semantic_cutoff -> score = similarity, else 0.0.
        3. Return the average score across all query words.
    """
    word_data = _get_syllabus_words_and_embeddings(syllabus_id, embed_fn)
    if not word_data:
        return 1.0  # No concepts stored → skip gate

    syllabus_words, syllabus_embs = word_data

    # Extract non-generic question words
    q_words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", question.lower()) if w not in GENERIC_WORDS]
    if not q_words:
        return 1.0  # Safe fallback if question has no content words

    try:
        q_embs = embed_fn(q_words, task="query")
    except TypeError:
        q_embs = embed_fn(q_words)

    similarities = []
    for q_word, q_emb in zip(q_words, q_embs):
        # 1. Exact match check
        if q_word in syllabus_words:
            similarities.append(1.0)
            continue

        # 2. Morphological match check
        morph_found = False
        for s_word in syllabus_words:
            if _is_morphological_match(q_word, s_word):
                similarities.append(1.0)
                morph_found = True
                break
        if morph_found:
            continue

        # 3. Semantic matching
        max_sim = 0.0
        for s_emb in syllabus_embs:
            sim = _cosine_similarity(q_emb, s_emb)
            if sim > max_sim:
                max_sim = sim

        # 4. Soft semantic cutoff to filter out background stylistic associations
        if max_sim >= semantic_cutoff:
            similarities.append(max_sim)
        else:
            similarities.append(0.0)

    return sum(similarities) / len(similarities)


# ---------------------------------------------------------------------------
# Public gate API
# ---------------------------------------------------------------------------

def validate_scope(
    question:              str,
    similarity:            float,
    syllabus_id:           Optional[str],
    embed_fn,
    high_sim_threshold:    float = 0.72,
    min_overlap_threshold: float = 0.24,
    semantic_cutoff:       float = 0.86,
) -> Dict[str, Any]:
    """
    Curriculum Scope Validator — deterministic pre-LLM gate.

    Blocks domain intrusions (like ML, Cloud, AI, IoT, NLP on a Cryptography
    syllabus) when their similarity score is high but their content words do
    not semantically overlap with the syllabus vocabulary.
    """
    # ── Guard 1: only activate when a specific syllabus is selected ──────────
    if not syllabus_id:
        return {"is_out_of_scope": False, "concept_overlap": 1.0, "reason": ""}

    # ── Guard 2: only activate when retriever already thinks it is relevant ──
    if similarity < high_sim_threshold:
        return {"is_out_of_scope": False, "concept_overlap": 1.0, "reason": ""}

    # ── Guard 3: silently skip if no concepts have been ingested yet ─────────
    if not load_scope_concepts(syllabus_id):
        return {"is_out_of_scope": False, "concept_overlap": 1.0, "reason": "No scope concepts stored"}

    # ── Compute semantic concept overlap ────────────────────────────────────
    overlap = compute_concept_overlap(question, syllabus_id, embed_fn, semantic_cutoff=semantic_cutoff)
    overlap = round(overlap, 4)

    if overlap < min_overlap_threshold:
        reason = (
            f"Concept overlap score {overlap:.2f} is below the minimum "
            f"threshold ({min_overlap_threshold:.2f}). The question concepts "
            f"do not align with the selected syllabus despite high retrieval "
            f"similarity — likely caused by shared generic academic vocabulary."
        )
        print(
            f"[ScopeValidator] REJECTED '{question[:60]}' | "
            f"sim={similarity:.3f} overlap={overlap:.3f}"
        )
        return {
            "is_out_of_scope": True,
            "concept_overlap":  overlap,
            "reason":           reason,
        }

    print(
        f"[ScopeValidator] PASSED '{question[:60]}' | "
        f"sim={similarity:.3f} overlap={overlap:.3f}"
    )
    return {
        "is_out_of_scope": False,
        "concept_overlap":  overlap,
        "reason":           "",
    }
