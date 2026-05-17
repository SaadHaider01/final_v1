"""
services/chunk_quality.py
--------------------------
Pre-embedding chunk quality gate.

Applied BEFORE chunks are sent to the vector database.
Rejects low-information chunks that would pollute semantic retrieval.

The root problem:
  Metadata header chunks like "Subject Name: Cryptography and Network Security"
  or "Credits: 4  L-T-P: 3-1-0" have high surface similarity to questions that
  mention keyword like "security", causing false STRONG_MATCHes.

Strategy:
  1. Hard reject pure header/admin metadata lines.
  2. Hard reject chunks with insufficient token density.
  3. Soft score: require minimum educational content signals.
"""

import re

# ── Minimum standards ────────────────────────────────────────────────────────
MIN_CHARS         = 80    # Absolute minimum character count
MIN_ALPHA_TOKENS  = 8     # Must have at least 8 real words
MIN_CONTENT_RATIO = 0.40  # At least 40% of the chunk must be non-metadata text

# ── Header / administrative field patterns ───────────────────────────────────
# These patterns identify lines that are pure metadata labels and values.
_HEADER_FIELDS = re.compile(
    r"^[^a-z\n]{0,30}"               # optional leading noise
    r"(?:"
    r"Subject\s*Name\s*[:\-]|"
    r"Course\s*Title\s*[:\-]|"
    r"Subject\s*Code\s*[:\-]|"
    r"Paper\s*Code\s*[:\-]|"
    r"Course\s*Code\s*[:\-]|"
    r"Code\s*[:\-]\s*[A-Z0-9]+|"
    r"Contact\s*(?:Hrs?)?\s*[:\-]|"
    r"Credits?\s*[:\-]|"
    r"L\s*[-–]\s*T\s*[-–]\s*P\s*[:\-]|"
    r"L-T-P|"
    r"Semester\s*[:\-]|"
    r"Total\s*Marks?\s*[:\-]|"
    r"Internal\s*(?:Assessment|Marks?)\s*[:\-]|"
    r"External\s*(?:Assessment|Marks?|Exam)\s*[:\-]|"
    r"End\s*Semester\s*Exam|"
    r"Mid\s*Semester|"
    r"Teaching\s*Scheme|"
    r"Examination\s*Scheme|"
    r"Credit\s*Points?|"
    r"Hours?\s*/\s*Week|"
    r"Pre-?requisite\s*[:\-]|"
    r"Category\s*[:\-]|"
    r"Department\s*[:\-]|"
    r"Faculty\s*[:\-]|"
    r"University\s*[:\-]"
    r")",
    re.IGNORECASE,
)

# A chunk is "mostly headers" if more than half its lines match header patterns
_HEADER_LINE = re.compile(
    r"^\s*(?:"
    r"(?:Subject|Course|Paper|Code)\s*(?:Name|Title|Code)?\s*[:\-]|"
    r"(?:Credits?|Contacts?|L-T-P|Hours?|Marks?)\s*[:\-]?|"
    r"(?:Internal|External|Total)\s*(?:Assessment|Marks?|Exam)\s*[:\-]?|"
    r"(?:Semester|Department|Faculty|University)\s*[:\-]?|"
    r"Teaching\s*Scheme|Examination\s*Scheme|Credit\s*Points?"
    r")\s*.*$",
    re.IGNORECASE,
)

# ── Educational content signals ──────────────────────────────────────────────
# Presence of these patterns strongly suggests real instructional content.
_EDUCATIONAL_SIGNALS = re.compile(
    r"\b(?:"
    # Core academic instruction words
    r"introduc(?:tion|ing|ed)|overview|concept|principle|theor(?:y|ies)|"
    r"algorithm|protocol|architecture|mechanism|technique|method(?:ology)?|"
    r"application|implementation|design|analysis|comparison|evaluation|"
    r"type[s]?|categor(?:y|ies)|classif(?:y|ication)|"
    # Action/learning verbs
    r"defin(?:e|ition)|explain|describ(?:e|ing)|understand|demonstrate|"
    r"compar(?:e|ison)|contrast|discuss|illustrat(?:e|ing)|analyz(?:e|ing)|"
    # Technical depth signals
    r"model|framework|structure|component|system|network|database|"
    r"encrypt(?:ion)?|decrypt(?:ion)?|secur(?:ity|e)|"
    r"program(?:ming)?|software|hardware|process(?:ing)?|"
    r"memory|storage|communication|transmission|"
    r"function|operation|procedure|workflow|pipeline"
    r")\b",
    re.IGNORECASE,
)

# ── Stopwords for token counting ─────────────────────────────────────────────
_STOPWORDS = frozenset([
    "the", "is", "are", "a", "an", "of", "in", "on", "to", "and", "or",
    "for", "with", "by", "as", "at", "from", "that", "this", "be", "was",
    "were", "it", "its", "into", "their", "there", "then", "has", "have",
    "had", "can", "will", "may", "which", "such", "etc", "i", "ii", "iii",
])


def _count_alpha_tokens(text: str) -> int:
    """Count meaningful alphabetic tokens (non-stopword words ≥ 3 chars)."""
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return sum(1 for t in tokens if t not in _STOPWORDS)


def _header_line_ratio(text: str) -> float:
    """Fraction of lines that look like metadata header fields."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return 1.0
    header_count = sum(1 for l in lines if _HEADER_LINE.match(l))
    return header_count / len(lines)


def is_low_information_chunk(text: str) -> bool:
    """
    Return True if this chunk should be REJECTED before embedding.

    A chunk is low-information if:
    1. Too short to carry any content.
    2. Primarily composed of metadata/header fields.
    3. Insufficient meaningful token count.
    4. No educational content signals at all.
    """
    t = text.strip()

    # Rule 1: Absolute minimum length
    if len(t) < MIN_CHARS:
        return True

    # Rule 2: Starts with a known header field (single-line metadata snippets)
    if _HEADER_FIELDS.match(t):
        # Allow if the rest of the text (after the header label) is rich enough
        # Split on first newline — if only one line, it's pure metadata
        lines = [l.strip() for l in t.splitlines() if l.strip()]
        if len(lines) <= 2:
            return True

    # Rule 3: Majority of lines are header fields
    header_ratio = _header_line_ratio(t)
    if header_ratio >= 0.60:
        return True

    # Rule 4: Insufficient meaningful tokens
    alpha_tokens = _count_alpha_tokens(t)
    if alpha_tokens < MIN_ALPHA_TOKENS:
        return True

    # Rule 5: No educational signals at all in the chunk
    # (catches things like phone numbers, addresses, timetables)
    if not _EDUCATIONAL_SIGNALS.search(t):
        # Give it a pass if it's long enough (>250 chars) — might be dense content
        # without using specific signal words (e.g., maths notation)
        if len(t) < 250:
            return True

    return False


def filter_chunks_for_embedding(chunks: list) -> tuple[list, int]:
    """
    Filter a list of (text, module_label) tuples before embedding.

    Returns:
        (filtered_chunks, rejected_count)
    """
    kept = []
    rejected = 0

    for item in chunks:
        # Accept both tuple (text, label) and plain str
        if isinstance(item, tuple):
            text, label = item[0], item[1]
        else:
            text, label = str(item), None

        if is_low_information_chunk(text):
            rejected += 1
            print(f"[ChunkQuality] REJECTED ({len(text)}ch, low-info): {text[:80]!r}")
        else:
            kept.append((text, label) if isinstance(item, tuple) else text)

    if rejected:
        print(f"[ChunkQuality] Kept {len(kept)}/{len(kept)+rejected} chunks "
              f"({rejected} low-information chunks purged)")

    return kept, rejected
