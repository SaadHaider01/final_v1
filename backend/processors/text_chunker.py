"""
processors/text_chunker.py
--------------------------
Smart syllabus chunker with unit-header detection.

Handles three syllabus formats:
  Format A — explicit keyword:  "Module 1", "Unit – 2", "UNIT I"
  Format B — table row number:  "1  Introduction: ..."
             (bare digit, optional whitespace, capitalised title ending in colon)
  Format C — no recognisable heading (fallback: sentence/line-length splitting)

Returns a list of (text, module_label) tuples so callers can store module
metadata alongside the chunk text.
"""

import re

# ── Heading patterns ───────────────────────────────────────────────────────────

# Format A: "Module 1", "UNIT – 2", "UNIT I", "Chapter 3"
_HEADING_A = re.compile(
    r"(?:^|\n)\s*(?:Module|Unit|Chapter)\s*[\-–:]?\s*(\d+|[IVXLC]+)\b",
    re.IGNORECASE,
)

# Format B: bare digit at line-start followed by a capitalised title and a colon
#   e.g.  "1  Introduction to Cyber Security:"
#         "2  Hackers and Cyber Crimes:"
_HEADING_B = re.compile(
    r"(?:^|\n)\s*(\d{1,2})\s+([A-Z][^:\n]{2,80}?):\s*",
)


def _split_into_sections(text: str):
    """
    Split syllabus text into (unit_label, section_text) pairs.

    Tries Format A first, then Format B. Falls back to treating the whole
    text as a single unnamed section.

    Returns list of (label_str_or_None, section_text).
    """
    text = text.replace("\r", "")

    # ── Try Format A ────────────────────────────────────────────────────────
    parts_a = _HEADING_A.split(text)
    # split() with a capturing group returns [before, g1, after, g1, after, ...]
    # For a non-capturing pattern it returns [before, after, after, ...]
    # We used a capturing group so: [pre, num, body, num, body, ...]

    # Re-search to get actual heading text (we need the full heading string,
    # not just the captured group).
    headings_a = _HEADING_A.findall(text)  # list of unit numbers
    if len(headings_a) >= 2:
        pieces = _HEADING_A.split(text)
        sections = []
        # pieces = [pre_text, num, body, num, body, ...]
        pre = pieces[0]
        if pre.strip():
            sections.append((None, pre.strip()))
        i = 1
        while i < len(pieces) - 1:
            num  = pieces[i].strip()
            body = pieces[i + 1].strip() if i + 1 < len(pieces) else ""
            sections.append((f"Unit {num}", body))
            i += 2
        if sections:
            return sections

    # ── Try Format B ────────────────────────────────────────────────────────
    headings_b = list(_HEADING_B.finditer(text))
    if len(headings_b) >= 2:
        sections = []
        for j, match in enumerate(headings_b):
            num   = match.group(1).strip()
            title = match.group(2).strip()
            label = f"Unit {num}: {title}"
            start = match.end()
            end   = headings_b[j + 1].start() if j + 1 < len(headings_b) else len(text)
            body  = text[start:end].strip()
            sections.append((label, body))
        # Preserve any text before the first heading
        pre = text[:headings_b[0].start()].strip()
        if pre:
            sections.insert(0, (None, pre))
        return sections

    # ── Fallback: no headings detected ─────────────────────────────────────
    return [(None, text.strip())]


def chunk_syllabus(text: str):
    """
    Returns a list of chunk strings.
    Preserved for backward compatibility with existing callers.
    """
    return [chunk for chunk, _ in chunk_syllabus_with_modules(text)]


def chunk_syllabus_with_modules(text: str):
    """
    Returns a list of (chunk_text, module_label_or_None) tuples.

    Each chunk is ≤ 220 characters. All chunks from the same unit share the
    same module_label so that vector store metadata can filter by unit.
    """
    sections = _split_into_sections(text)
    result   = []

    for label, body in sections:
        if not body:
            continue

        # Split body into lines, then further split on bullet separators
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        for line in lines:
            parts = re.split(r"[•·\-–]\s+", line)
            for p in parts:
                p = p.strip()
                if len(p) < 20:
                    continue  # skip tiny fragments

                # Force max chunk size ~ 220 chars
                while len(p) > 220:
                    result.append((p[:220], label))
                    p = p[220:]
                if p:
                    result.append((p, label))

    return result
