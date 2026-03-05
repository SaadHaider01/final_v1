"""
services/module_detector.py
----------------------------
Feature 1: Multi-module detection.

Scans top_chunks returned by the vector store query.
Any chunk whose similarity meets or exceeds the threshold AND
whose 'module' metadata is not empty / unknown contributes a
unique module name to the final list.

This module has NO side effects and does NOT touch the embedder,
LLM, or ChromaDB — it is a pure function.
"""

from config import MODULE_SIMILARITY_THRESHOLD


def detect_modules(
    top_chunks: list,
    threshold: float = None,
) -> list:
    """
    Return de-duplicated list of module names from top_chunks where
    chunk similarity >= threshold.

    Args:
        top_chunks: list of dicts with keys 'similarity', 'module'
        threshold:  minimum similarity to include (defaults to config value)

    Returns:
        list of unique module name strings (may be empty)
    """
    if threshold is None:
        threshold = MODULE_SIMILARITY_THRESHOLD

    seen: set = set()
    modules: list = []

    for chunk in top_chunks:
        sim = chunk.get("similarity", 0.0)
        module = chunk.get("module")

        if sim < threshold:
            continue

        if not module:
            continue

        module = str(module).strip()

        if not module or module.lower() in ("unknown", "none", ""):
            continue

        if module not in seen:
            seen.add(module)
            modules.append(module)

    return modules
