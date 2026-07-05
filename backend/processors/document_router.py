r"""
processors/document_router.py
------------------------------
Lightweight document type detector.

Sits between text extraction and the parsers.
Does NOT extract data -- classification only.

Returns one of three document types:
  - "LEGACY_SUBJECT"           -- legacy single-subject syllabus (MAKAUT, etc.)
  - "STRUCTURED_SUBJECT"       -- one structured course (Course Title, CO-PO, etc.)
  - "MULTI_SUBJECT_CURRICULUM" -- full curriculum with multiple Course Title markers

NOTE: All word-boundary patterns use \s* (zero or more spaces) between words
because PDF text extractors commonly strip inter-word spaces, producing
"CourseTitle:" instead of "Course Title:".
"""

import re

# -----------------------------------------------------------
# COURSE TITLE MARKER
# Matches: "CourseTitle:", "Course Title:", "CourseName:", "Course Name:",
#          "PaperTitle:", "Paper Title:", "SubjectTitle:", "Subject Title:"
# Case-insensitive. Must appear at start of a line.
# \s* handles PDF extraction artefacts where spaces are stripped.
# -----------------------------------------------------------
_COURSE_TITLE_MARKER = re.compile(
    r"^\s*(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]",
    re.IGNORECASE | re.MULTILINE,
)

# -----------------------------------------------------------
# STRUCTURED INDICATORS (regex-based to handle no-space PDFs)
# Each is a compiled pattern with \s* between words.
# Presence of 2+ matches signals a structured (AICTE-style) document.
# -----------------------------------------------------------
_STRUCTURED_INDICATOR_PATTERNS = [
    re.compile(r"Course\s*Outcomes?",             re.IGNORECASE),
    re.compile(r"CO\s*-\s*PO\s*Mapping",         re.IGNORECASE),
    re.compile(r"CO\s*-?\s*PO",                  re.IGNORECASE),
    re.compile(r"Course\s*Objectives?",           re.IGNORECASE),
    re.compile(r"Course\s*Title",                 re.IGNORECASE),
    re.compile(r"Program\s*Outcomes?",            re.IGNORECASE),
    re.compile(r"\bPSO\b",                        re.IGNORECASE),
    re.compile(r"Syllabus\s*and\s*Curricular\s*Mapping", re.IGNORECASE),
    re.compile(r"Mapping\s*of\s*COs",             re.IGNORECASE),
    re.compile(r"Course\s*Articulation\s*Matrix", re.IGNORECASE),
    re.compile(r"Bloom\s*['']?s?\s*Taxonomy",     re.IGNORECASE),
]


def detect_document_type(text: str, source: str = "unknown") -> str:
    """
    Classify the extracted text into one of:
      - "LEGACY_SUBJECT"
      - "STRUCTURED_SUBJECT"
      - "MULTI_SUBJECT_CURRICULUM"

    Args:
        text:   The full extracted plain-text content.
        source: Human-readable label for logging (e.g. "PDF", "URL", "Paste").

    Returns:
        One of the three document type strings.
    """
    print(f"[Router] Input Source: {source}")
    print(f"[Router] Text Length: {len(text)} chars")

    # -- Step 1: Count Course Title markers ------------------
    title_matches = _COURSE_TITLE_MARKER.findall(text)
    title_count = len(title_matches)
    print(f"[Router] Detected Course Title markers: {title_count}")

    if title_count >= 2:
        doc_type = "MULTI_SUBJECT_CURRICULUM"
        print(f"[Router] Document Type: {doc_type}")
        return doc_type

    # -- Step 2: Score structured indicators (regex, handles no-space PDFs) --
    structured_score = sum(
        1 for pat in _STRUCTURED_INDICATOR_PATTERNS if pat.search(text)
    )
    print(f"[Router] Structured indicator score: {structured_score}")

    if title_count == 1 or structured_score >= 2:
        doc_type = "STRUCTURED_SUBJECT"
        print(f"[Router] Document Type: {doc_type}")
        return doc_type

    # -- Step 3: Default to legacy ---------------------------
    doc_type = "LEGACY_SUBJECT"
    print(f"[Router] Document Type: {doc_type}")
    return doc_type
