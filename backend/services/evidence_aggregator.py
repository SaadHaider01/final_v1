"""
services/evidence_aggregator.py
---------------------------------
Multi-chunk evidence aggregation — v2.

Receives the RAW Top-K chunks (before dedup / smart-filter) and computes
four evidence signals that, together with a nonlinear density multiplier,
produce a final confidence score used by Gate 2 of the decision pipeline.

Improvements over v1
---------------------
1. Minimum Supporting Evidence Rule   — hard gate before confidence evaluation
2. Module Consistency on support-only — computed only from qualifying chunks
3. Nonlinear Evidence Density         — applied as a multiplicative modifier
4. Similarity Stability               — replaces variance (more interpretable)
5. Expanded evidence_debug output     — richer debugging fields

This module is:
  - Curriculum-agnostic      (no subject / department hardcoding)
  - Stateless / side-effect free (pure function)
  - Backward-compatible      (gracefully handles < 2 chunks)
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from config import (
    EVIDENCE_ACCEPTANCE_THR,
    EVIDENCE_WEIGHTS,
    MIN_SUPPORTING_CHUNKS,
    EVIDENCE_DENSITY_CURVE,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chunk_sims(chunks: List[Dict]) -> List[float]:
    """Return a list of similarity floats from a chunk list."""
    return [float(c.get("similarity", 0.0)) for c in chunks]


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _extract_concepts(text: str) -> set:
    """
    Lightweight concept extraction: unigrams (4+ chars) and bigrams.

    Completely language-agnostic — no stopword list, no subject vocabulary.
    """
    tokens = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    concepts: set = set(tokens)
    for i in range(len(tokens) - 1):
        concepts.add(f"{tokens[i]}_{tokens[i+1]}")
    return concepts


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union        = len(set_a | set_b)
    return intersection / union if union else 0.0


# ---------------------------------------------------------------------------
# Individual signal computers
# ---------------------------------------------------------------------------

def _signal_avg_similarity(sims: List[float]) -> float:
    """
    Mean cosine similarity across ALL retrieved chunks.
    Represents the overall breadth of semantic support.
    """
    return _mean(sims)


def _signal_similarity_stability(supporting_sims: List[float]) -> float:
    """
    Improvement 4 — replaces the old variance metric.

    Measures how tightly clustered the SUPPORTING chunk scores are.

    Stability = 1 - (max_supporting_sim - min_supporting_sim)

    Intuition:
      [0.91, 0.90, 0.89, 0.88] → range = 0.03 → stability = 0.97  (very stable)
      [0.91, 0.75, 0.73, 0.72] → range = 0.19 → stability = 0.81  (moderate)
      [0.91, 0.72, 0.72, 0.72] → range = 0.19 → same result

    Returns 1.0 for a single supporting chunk (no spread to penalise).
    """
    if len(supporting_sims) < 2:
        return 1.0
    spread = max(supporting_sims) - min(supporting_sims)
    # spread is always in [0, 1]; higher spread → lower stability
    return round(max(0.0, 1.0 - spread), 4)


def _signal_module_consistency(supporting_chunks: List[Dict]) -> float:
    """
    Improvement 2 — computed exclusively on SUPPORTING chunks.

    Fraction of supporting chunks that share the most common module.

    [Module2, Module2, Module2, Module2] → 4/4 = 1.00  (strong coherence)
    [Module2, Module4, Module6, Module7] → 1/4 = 0.25  (dispersed evidence)

    Chunks with unknown / empty module are excluded from the majority count
    but still count toward the denominator.
    """
    if not supporting_chunks:
        return 0.0

    module_counts: Dict[str, int] = {}
    for c in supporting_chunks:
        mod = (c.get("module") or "unknown").strip().lower()
        if mod in ("", "unknown", "none"):
            mod = "__unknown__"
        module_counts[mod] = module_counts.get(mod, 0) + 1

    # Only known modules contribute to the majority count
    known = {m: cnt for m, cnt in module_counts.items() if m != "__unknown__"}
    if not known:
        return 0.0  # all unknown → no module signal

    majority_count = max(known.values())
    return majority_count / len(supporting_chunks)


def _signal_concept_agreement(chunks: List[Dict]) -> float:
    """
    Pairwise average Jaccard similarity of concept bags across ALL chunks.

    If multiple chunks share the same core concepts, the question has
    consistent multi-source backing.

    Returns 0.0 for fewer than 2 chunks (no pair to compare).
    """
    if len(chunks) < 2:
        return 0.0

    concept_bags = [_extract_concepts(c.get("text", "")) for c in chunks]

    pairs: List[float] = []
    for i in range(len(concept_bags)):
        for j in range(i + 1, len(concept_bags)):
            pairs.append(_jaccard(concept_bags[i], concept_bags[j]))

    return _mean(pairs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_evidence(chunks: List[Dict]) -> Dict[str, Any]:
    """
    Compute multi-chunk evidence signals and return a structured EvidenceReport.

    Args:
        chunks: Raw Top-K retrieved chunks (before dedup / smart-filter).
                Each chunk must have at least ``similarity`` (float) and
                ``text`` (str) keys.  ``module`` is optional.

    Returns:
        EvidenceReport with keys:
            best_similarity      float  – highest individual similarity
            average_similarity   float  – mean similarity across all chunks
            supporting_chunks    int    – count of chunks above acceptance threshold
            supporting_ratio     float  – supporting_chunks / total (density)
            module_consistency   float  – majority-module fraction (support-only)
            concept_agreement    float  – mean pairwise Jaccard of concepts
            similarity_stability float  – 1 - (max_sup_sim - min_sup_sim)
            final_confidence     float  – base_confidence * density_modifier
            signal_scores        dict   – per-signal normalised values
            chunks_analysed      int    – total raw chunks examined
            insufficient_evidence bool – True when MIN_SUPPORTING_CHUNKS not met
            insufficient_reason  str   – human-readable rejection reason
    """
    if not chunks:
        return _null_report()

    sims = _chunk_sims(chunks)
    k    = len(chunks)

    # ── Identify supporting chunks ────────────────────────────────────────────
    supporting_chunks = [
        c for c in chunks
        if float(c.get("similarity", 0.0)) >= EVIDENCE_ACCEPTANCE_THR
    ]
    supporting_sims   = [float(c.get("similarity", 0.0)) for c in supporting_chunks]
    supporting_count  = len(supporting_chunks)
    density_ratio     = supporting_count / k

    # ── Improvement 1: Minimum Supporting Evidence Rule ──────────────────────
    # Hard gate: if too few chunks qualify, reject immediately without computing
    # confidence.  This prevents a single high-scoring isolated chunk from
    # passing Gate 2 on its own.
    if supporting_count < MIN_SUPPORTING_CHUNKS:
        return _insufficient_report(
            sims=sims,
            supporting_count=supporting_count,
            k=k,
            density_ratio=density_ratio,
        )

    # ── Compute individual signals ────────────────────────────────────────────
    avg_sim      = _signal_avg_similarity(sims)
    sim_stab     = _signal_similarity_stability(supporting_sims)   # Improvement 4
    mod_consist  = _signal_module_consistency(supporting_chunks)    # Improvement 2
    concept_agr  = _signal_concept_agreement(chunks)

    signal_scores = {
        "avg_similarity":     avg_sim,
        "sim_stability":      sim_stab,
        "module_consistency": mod_consist,
        "concept_agreement":  concept_agr,
    }

    # ── Base confidence (weighted sum of 4 signals, no density) ──────────────
    w = EVIDENCE_WEIGHTS
    base_confidence = (
        w.get("avg_similarity",     0.40) * avg_sim     +
        w.get("sim_stability",      0.27) * sim_stab    +
        w.get("module_consistency", 0.20) * mod_consist  +
        w.get("concept_agreement",  0.13) * concept_agr
    )

    # ── Improvement 3: Nonlinear Evidence Density Multiplier ─────────────────
    # density_ratio ** EVIDENCE_DENSITY_CURVE produces a concave curve that
    # heavily penalises low density without linearly capping high density.
    #   ratio=0.20 → modifier≈0.35   ratio=0.40 → modifier≈0.58
    #   ratio=0.80 → modifier≈0.86   ratio=1.00 → modifier=1.00
    density_modifier = density_ratio ** EVIDENCE_DENSITY_CURVE
    final_confidence = round(
        min(1.0, max(0.0, base_confidence * density_modifier)), 4
    )

    # Raw stability value for debug (before normalisation)
    stability_raw = (
        round(max(supporting_sims) - min(supporting_sims), 4)
        if len(supporting_sims) >= 2 else 0.0
    )

    return {
        # ── Improvement 5: expanded debug output ────────────────────────────
        "best_similarity":      round(max(sims), 4),
        "average_similarity":   round(avg_sim, 4),
        "supporting_chunks":    supporting_count,
        "supporting_ratio":     round(density_ratio, 4),
        "module_consistency":   round(mod_consist, 4),
        "concept_agreement":    round(concept_agr, 4),
        "similarity_stability": stability_raw,     # raw spread (lower = more stable)
        "final_confidence":     final_confidence,
        # ── Internal detail ─────────────────────────────────────────────────
        "signal_scores":        {k: round(v, 4) for k, v in signal_scores.items()},
        "density_modifier":     round(density_modifier, 4),
        "base_confidence":      round(base_confidence, 4),
        "chunks_analysed":      k,
        "insufficient_evidence": False,
        "insufficient_reason":   "",
    }


# ---------------------------------------------------------------------------
# Private report builders
# ---------------------------------------------------------------------------

def _insufficient_report(
    sims: List[float],
    supporting_count: int,
    k: int,
    density_ratio: float,
) -> Dict[str, Any]:
    """
    Return a rejection report when MIN_SUPPORTING_CHUNKS is not satisfied.
    final_confidence is 0.0 to guarantee Gate 2 rejection.
    """
    reason = (
        f"Insufficient supporting evidence: only {supporting_count} of {k} "
        f"retrieved chunks exceeded the acceptance threshold "
        f"({EVIDENCE_ACCEPTANCE_THR:.0%}). "
        f"At least {MIN_SUPPORTING_CHUNKS} supporting chunks are required."
    )
    return {
        "best_similarity":      round(max(sims), 4) if sims else 0.0,
        "average_similarity":   round(_mean(sims), 4),
        "supporting_chunks":    supporting_count,
        "supporting_ratio":     round(density_ratio, 4),
        "module_consistency":   0.0,
        "concept_agreement":    0.0,
        "similarity_stability": 0.0,
        "final_confidence":     0.0,
        "signal_scores": {
            "avg_similarity":     round(_mean(sims), 4),
            "sim_stability":      0.0,
            "module_consistency": 0.0,
            "concept_agreement":  0.0,
        },
        "density_modifier":      round(density_ratio ** EVIDENCE_DENSITY_CURVE, 4),
        "base_confidence":       0.0,
        "chunks_analysed":       k,
        "insufficient_evidence": True,
        "insufficient_reason":   reason,
    }


def _null_report() -> Dict[str, Any]:
    """Return a zeroed report when no chunks are available."""
    return {
        "best_similarity":      0.0,
        "average_similarity":   0.0,
        "supporting_chunks":    0,
        "supporting_ratio":     0.0,
        "module_consistency":   0.0,
        "concept_agreement":    0.0,
        "similarity_stability": 0.0,
        "final_confidence":     0.0,
        "signal_scores": {
            "avg_similarity":     0.0,
            "sim_stability":      0.0,
            "module_consistency": 0.0,
            "concept_agreement":  0.0,
        },
        "density_modifier":      0.0,
        "base_confidence":       0.0,
        "chunks_analysed":       0,
        "insufficient_evidence": True,
        "insufficient_reason":   "No chunks available.",
    }
