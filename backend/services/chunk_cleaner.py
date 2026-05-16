"""
services/chunk_cleaner.py
--------------------------
Post-retrieval chunk cleaner.

Applied AFTER vector search, BEFORE frontend rendering.
Removes noisy chunks that slipped through the ingestion filter:
  - Publisher / bibliographic entries
  - Pure metadata fragments (credits, contacts)
  - Malformed / trivially short chunks
  - Accreditation noise

This is the final quality gate before the UI displays results.
"""

import re


# ── Reference / bibliographic patterns ──────────────────────────────────────

_PUBLISHER_KW = re.compile(
    r"Publishing|Publishers?|Press|Edition|McGraw|Pearson|Wiley|Springer|"
    r"Elsevier|Oxford|Cambridge|Prentice|Tata|Jaico|Housing|"
    r"\bPHI\b|\bEPH\b|\bTMH\b|\bSPD\b|\bBPB\b|ISBN",
    re.IGNORECASE,
)

_BIBLIO_SIGNAL = re.compile(
    r"""\bby\s+[A-Z][a-z]"""               # "by Reynolds"
    r"""|\u201c[^\u201d]{5,}\u201d"""       # curly-quoted title
    r'''|"[^"]{5,}"'''                       # straight-quoted
    r"""|'[^']{5,}'"""                       # single-quoted
    r"""|\b\d{1,2}(?:st|nd|rd|th)\s+Ed"""  # "2nd Edition"
    r"""|\bISBN\b""",
    re.IGNORECASE,
)

# Pure metadata fragments (nothing of semantic value)
_META_FRAGMENT = re.compile(
    r"^(?:Credits?|Contacts?|L[\-–]T[\-–]P|Hours?|Marks?|Scheme|"
    r"Course\s*Code|Subject\s*Code|Paper\s*Code)\s*[:\-]?\s*[\d\w\-]*\s*$",
    re.IGNORECASE,
)

# Correlation matrix rows
_MATRIX_ROW = re.compile(
    r"^(?:\s*(?:\d+(?:\.\d+)?)\s+){4,}\d+(?:\.\d+)?\s*$",
)

# CO/PO mapping noise
_CO_PO_NOISE = re.compile(
    r"^(?:CO\d+|PO\d+)\s*[-:]\s*(?:CO\d+|PO\d+)\s*$",
    re.IGNORECASE,
)


def _is_noisy_chunk(text: str) -> bool:
    """Return True if the chunk should be suppressed from the frontend."""
    t = text.strip()
    
    # Too short to be meaningful
    if len(t) < 30:
        return True
    
    # Pure metadata
    if _META_FRAGMENT.match(t):
        return True
    
    # Correlation matrix row
    if _MATRIX_ROW.match(t):
        return True
    
    # CO-PO pair noise
    if _CO_PO_NOISE.match(t):
        return True
    
    # Short bibliographic entries (reference books)
    if len(t) < 200:
        if _PUBLISHER_KW.search(t) and _BIBLIO_SIGNAL.search(t):
            return True
    
    return False


def clean_retrieved_chunks(chunks: list) -> list:
    """
    Filter a list of retrieved chunk dicts.

    Each chunk dict is expected to have at minimum a 'text' key.
    Returns only chunks that pass the noise filter.

    Args:
        chunks: list of dicts with keys like text, distance, similarity, module

    Returns:
        Filtered list of chunk dicts.
    """
    cleaned = []
    removed = 0
    
    for chunk in chunks:
        text = chunk.get("text", "").strip()
        if _is_noisy_chunk(text):
            removed += 1
            continue
        cleaned.append(chunk)
    
    if removed:
        print(f"[Chunk Cleaner] Removed {removed} noisy chunk(s), kept {len(cleaned)}")
    
    return cleaned
