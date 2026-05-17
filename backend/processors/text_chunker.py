"""
processors/text_chunker.py
--------------------------
Domain-agnostic syllabus chunker with unit-header detection.

Handles three syllabus formats:
  Format A — explicit keyword:  "Module 1", "Unit – 2", "UNIT I"
  Format B — table row number:  "1  Introduction: ..."
             (bare digit, optional whitespace, capitalised title ending in colon)
  Format C — no recognisable heading (fallback: sentence/line-length splitting)

Returns a list of (text, module_label) tuples so callers can store module
metadata alongside the chunk text.

DESIGN PRINCIPLE: This module is DOMAIN-AGNOSTIC. It must work identically
for any subject — computer science, biology, literature, law, etc.
No subject-specific hardcoding is permitted.
"""

import re

# ── Pre-processing: normalise typography ──────────────────────────────────────

# Generic: single letter + dash/en-dash + word  →  collapse to hyphen
#   Matches any pattern like "E – Commerce", "X – Ray", "N – gram"
#   where a single letter is separated from the next word by a spaced dash.
_SINGLE_LETTER_DASH = re.compile(
    r"\b([A-Za-z])\s*[–—]\s*(\w)", 
)

# Normalise lecture-hour markers  "[ 3 L ]" / "[10]" / "[ 2L ]" → ""
_LECTURE_HOURS = re.compile(r"\[\s*\d+\s*L?\s*\]", re.IGNORECASE)

# Course metadata lines — noise for embeddings, common across all university syllabi.
# Matches lines containing teaching scheme, marks breakdown, credit info, etc.
_COURSE_META = re.compile(
    r"(?:^|\n)[^\n]*?(?:"
    r"Teaching Scheme|Examination Scheme|Maximum Marks|Credit Points?|"
    r"Mid Semester|End Semester Exam|Assignment and Quiz|"
    r"Theory:\s*\d+\s*hrs?|Tutorial:\s*\d+\s*L|Practical:\s*(?:NIL|\d+)|"
    r"Duration:\s*\d+\s*months?|"
    r"Name of the Course:|Course Code:|"
    r"Contacts:\s*\d+\s*L|"
    r"Hrs/Unit|Marks/Unit|"
    r"Syllabus\s*and\s*Curricular\s*Mapping(?:forB\.Tech)?|Effective\s*from\s*Acdemic\s*Session|University\s*Syllabus:?"
    r")[^\n]*",
    re.IGNORECASE,
)

# University header/footer noise (e.g., Page: 116/123 Maulana Abul Kalam Azad University...)
_UNIVERSITY_HEADER = re.compile(
    r"(?:^|\n)\s*(?:Page:\s*\d+/\d+\s+)?[^\n]*?(?:University\s*of\s*Technology|Formerly\s*West\s*Bengal|Syllabus\s*and\s*Curricular)[^\n]*",
    re.IGNORECASE,
)

# Correlation matrices (CO/PO mapping rows full of numbers like "3.00 2.00 2.00 1.75 0 1.00")
# Matches a sequence of at least 5 numbers (floats or ints) separated by spaces.
_CORRELATION_MATRIX = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s+){4,}\d+(?:\.\d+)?\b",
)


def _normalise(text: str) -> str:
    """
    Clean up syllabus text before chunking.
    
    All transformations here are domain-agnostic:
    - Normalise unicode dashes to ASCII hyphens
    - Collapse single-letter-dash-word compounds (E – Commerce → E-Commerce)
    - Remove lecture-hour markers (noise for embeddings)
    - Remove course metadata lines (teaching scheme, marks, credits)
    - Collapse excessive whitespace
    """
    text = text.replace("\r", "")
    
    # Step 1: Collapse single-letter-dash-word compounds generically
    #   "E – Commerce" → "E-Commerce", "X – Ray" → "X-Ray"
    text = _SINGLE_LETTER_DASH.sub(r"\1-\2", text)
    
    # Step 2: Normalise ALL remaining en-dashes (–) and em-dashes (—) to hyphens
    #   This preserves readability while eliminating unicode inconsistencies
    text = text.replace("–", "-").replace("—", "-")
    
    # Step 3: Remove lecture-hour markers (noise for embeddings)
    text = _LECTURE_HOURS.sub("", text)

    # Step 4: Remove course metadata lines, headers, and matrices
    text = _COURSE_META.sub("", text)
    text = _UNIVERSITY_HEADER.sub("", text)
    text = _CORRELATION_MATRIX.sub("", text)
    
    # Step 5: Collapse excessive whitespace (but keep newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse 3+ consecutive newlines to 2 (keeps section breaks readable)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text


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

    # ── Try Format A ────────────────────────────────────────────────────────
    headings_a = _HEADING_A.findall(text)  # list of unit numbers
    if len(headings_a) >= 1:  # Handle even single-unit syllabi
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


# ── Topic-level splitting ─────────────────────────────────────────────────────

# Detect numbered topic starts: "1.", "2.", "10." or bare "1 ", "2 " at start-of-line
_TOPIC_NUM = re.compile(r"(?:^|\n)\s*(\d{1,2})(?:\.|\s+(?=[A-Z]))\s*")


def _split_section_into_topics(body: str, unit_label: str | None):
    """
    Split a section body into topic-level chunks.

    Within each unit, topics are typically numbered: "1. Overview, ...",
    "2. Technologies : ...".  We split on those numbered markers so each
    chunk represents one complete topic (with all its sub-topics intact).

    This approach is domain-agnostic — it relies on structural numbering
    patterns common across all academic syllabi, not subject-specific keywords.

    Returns list of (chunk_text, unit_label).
    """
    # --- FINAL FIX 1: REFERENCE POLLUTION ---
    # Strip any reference sections from this module's body.
    # The next module boundary is handled by the parent caller.
    lines = body.split("\n")
    clean_lines = []
    _REF_HEADING_RE = re.compile(
        r"^(?:\d+\.?\s*)?(?:Text\s*books?|References?|Reference\s*books?|Suggested\s*Readings?|Bibliography)(?:\s*and\s*reference\s*books?)?\s*:?",
        re.IGNORECASE
    )
    for line in lines:
        if _REF_HEADING_RE.match(line.strip()):
            break  # Discard the rest of this module's body
        clean_lines.append(line)
    
    body = "\n".join(clean_lines).strip()
    if not body:
        return []

    topics = list(_TOPIC_NUM.finditer(body))

    if len(topics) >= 2:
        chunks = []
        # Text before the first numbered topic (rare but possible)
        pre = body[:topics[0].start()].strip()
        if pre and len(pre) >= 20:
            chunks.append((pre, unit_label))

        for j, match in enumerate(topics):
            start = match.start()
            end   = topics[j + 1].start() if j + 1 < len(topics) else len(body)
            topic_text = body[start:end].strip()
            if topic_text and len(topic_text) >= 20:
                chunks.append((topic_text, unit_label))
        return chunks

    # No numbered topics found — split on newlines as fallback
    # This handles unstructured prose syllabi (any subject)
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 500 and current:
            if len(current.strip()) >= 20:
                chunks.append((current.strip(), unit_label))
            current = line
        else:
            current = f"{current}\n{line}".strip() if current else line
    if current.strip() and len(current.strip()) >= 20:
        chunks.append((current.strip(), unit_label))

    return chunks if chunks else ([(body.strip(), unit_label)] if len(body.strip()) >= 20 else [])


def chunk_syllabus(text: str):
    """
    Returns a list of chunk strings.
    Preserved for backward compatibility with existing callers.
    """
    return [chunk for chunk, _ in chunk_syllabus_with_modules(text)]


def chunk_syllabus_with_modules(text: str):
    """
    Returns a list of (chunk_text, module_label_or_None) tuples.

    Each chunk is one complete topic (e.g. "1. Overview, Definitions, ...").
    If a topic exceeds 500 characters, it is split at sentence boundaries.
    All chunks from the same unit share the same module_label so that
    vector store metadata can filter by unit.
    
    This function is domain-agnostic — it works identically for any subject.
    """
    text = _normalise(text)
    sections = _split_into_sections(text)
    result   = []

    for label, body in sections:
        if not body:
            continue

        # Split into topic-level chunks first
        topic_chunks = _split_section_into_topics(body, label)

        for chunk_text, chunk_label in topic_chunks:
            # Infer module label from chunk content if missing (e.g. "Firewall - Introduction" -> "Firewall")
            if not chunk_label:
                first_line = chunk_text.strip().split("\n")[0]
                clean_title = re.sub(r"^(\d{1,2}\.?\s*|\-\s*|•\s*)", "", first_line)
                implicit_title = re.split(r"[,:;.]|\s*-\s*", clean_title)[0].strip()
                if 3 <= len(implicit_title) <= 60:
                    chunk_label = implicit_title
                else:
                    chunk_label = "Unknown"

            # If chunk is small enough, keep as-is
            if len(chunk_text) <= 500:
                result.append((chunk_text, chunk_label))
            else:
                # Split long topics at sentence boundaries (period + space)
                sentences = re.split(r"(?<=\.)\s+", chunk_text)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 > 500 and current:
                        if len(current.strip()) >= 20:
                            result.append((current.strip(), chunk_label))
                        current = sent
                    else:
                        current = f"{current} {sent}".strip() if current else sent
                if current.strip() and len(current.strip()) >= 20:
                    result.append((current.strip(), chunk_label))

    return result
