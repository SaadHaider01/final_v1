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
from debug_logger import dsection, dlog, dlist, dtable, derror, ddivider

# -----------------------------------------------------------
# COURSE TITLE MARKER
# -----------------------------------------------------------
_COURSE_TITLE_MARKER = re.compile(
    r"^\s*(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]",
    re.IGNORECASE | re.MULTILINE,
)

# -----------------------------------------------------------
# STRUCTURED INDICATORS (regex-based to handle no-space PDFs)
# -----------------------------------------------------------
_STRUCTURED_INDICATOR_LABELS = [
    ("Course Outcomes",             re.compile(r"Course\s*Outcomes?",             re.IGNORECASE)),
    ("CO-PO Mapping",               re.compile(r"CO\s*-\s*PO\s*Mapping",         re.IGNORECASE)),
    ("CO-PO",                       re.compile(r"CO\s*-?\s*PO",                  re.IGNORECASE)),
    ("Course Objectives",           re.compile(r"Course\s*Objectives?",           re.IGNORECASE)),
    ("Course Title",                re.compile(r"Course\s*Title",                 re.IGNORECASE)),
    ("Program Outcomes",            re.compile(r"Program\s*Outcomes?",            re.IGNORECASE)),
    ("PSO",                         re.compile(r"\bPSO\b",                        re.IGNORECASE)),
    ("Syllabus and Curricular Map", re.compile(r"Syllabus\s*and\s*Curricular\s*Mapping", re.IGNORECASE)),
    ("Mapping of COs",              re.compile(r"Mapping\s*of\s*COs",             re.IGNORECASE)),
    ("Course Articulation Matrix",  re.compile(r"Course\s*Articulation\s*Matrix", re.IGNORECASE)),
    ("Bloom Taxonomy",              re.compile(r"Bloom\s*[''s]*\s*Taxonomy",      re.IGNORECASE)),
]
_STRUCTURED_INDICATOR_PATTERNS = [pat for _, pat in _STRUCTURED_INDICATOR_LABELS]


def detect_document_type(text: str, source: str = "unknown") -> str:
    """
    Classify the extracted text into one of:
      - "LEGACY_SUBJECT"
      - "STRUCTURED_SUBJECT"
      - "MULTI_SUBJECT_CURRICULUM"
    """
    # Always print current/original logging style so tests pass and standard outputs remain
    print(f"[Router] Input Source: {source}")
    print(f"[Router] Text Length: {len(text)} chars")

    title_matches = _COURSE_TITLE_MARKER.findall(text)
    title_count = len(title_matches)
    print(f"[Router] Detected Course Title markers: {title_count}")

    structured_score = sum(1 for _, pat in _STRUCTURED_INDICATOR_LABELS if pat.search(text))

    # Gated detailed logs
    from config import DEBUG_MODE
    if DEBUG_MODE:
        dsection("Router")
        dlog("Router", "Input Source", source)
        dlog("Router", "Text Length", f"{len(text):,} chars")
        dlog("Router", "Course Title markers found", title_count)

    if title_count >= 2:
        doc_type = "MULTI_SUBJECT_CURRICULUM"
        print(f"[Router] Document Type: {doc_type}")
        if DEBUG_MODE:
            dlog("Router", "Decision", f"{doc_type}  (reason: {title_count} Course Title markers)")
        return doc_type

    print(f"[Router] Structured indicator score: {structured_score}")

    if DEBUG_MODE:
        hit_labels = []
        for label, pat in _STRUCTURED_INDICATOR_LABELS:
            found = bool(pat.search(text))
            hit_labels.append(f"{'YES' if found else 'NO ':3s}  {label}")
        dlog("Router", "Structured indicator score", f"{structured_score}/{len(_STRUCTURED_INDICATOR_LABELS)}")
        dlist("Router", "Indicators", hit_labels)

    if title_count == 1 or structured_score >= 2:
        doc_type = "STRUCTURED_SUBJECT"
        print(f"[Router] Document Type: {doc_type}")
        if DEBUG_MODE:
            reason = "1 Course Title marker" if title_count == 1 else f"score={structured_score}"
            dlog("Router", "Decision", f"{doc_type}  (reason: {reason})")
            dlog("Router", "Parser selected", "Structured Curriculum Parser")
        return doc_type

    # -- Step 3: Default to legacy ---------------------------
    doc_type = "LEGACY_SUBJECT"
    print(f"[Router] Document Type: {doc_type}")
    if DEBUG_MODE:
        if title_count == 0 and structured_score < 2:
            derror("Router", "No structured indicators found", "Routing to legacy parser")
        dlog("Router", "Decision", f"{doc_type}")
        dlog("Router", "Parser selected", "Legacy Curriculum Segmenter")
    return doc_type
