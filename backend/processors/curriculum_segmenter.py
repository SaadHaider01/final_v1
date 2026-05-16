"""
processors/curriculum_segmenter.py
------------------------------------
Curriculum-driven hierarchy extractor.

Dynamically detects from any university curriculum PDF:
  Department → Semester → Subject → Elective Type → Module list

DESIGN PRINCIPLE:
  - NO hardcoded departments, semesters, subjects, universities, or course codes.
  - Operates purely on structural/syntactic indicators common across all engineering
    and management syllabi (MAKAUT, VTU, AICTE, ANNA, etc.).

Returns a list of syllabus block dicts ready for selective ingestion.
"""

import re
import hashlib


# ═══════════════════════════════════════════════════════════════════
# PRE-CLEANING — strip noise BEFORE parsing
# ═══════════════════════════════════════════════════════════════════

# CO/PO correlation matrix rows (5+ numbers separated by spaces)
_MATRIX_ROW = re.compile(
    r"^\s*(?:CO\d+|PO\d+)?\s*(?:\d+(?:\.\d+)?\s+){4,}\d+(?:\.\d+)?\s*$",
    re.MULTILINE,
)

# Bibliography / reference book lines
_BIBLIO_LINE = re.compile(
    r"(?:^|\n)[^\n]*?(?:"
    r"Publishing|Publishers?|Press|Edition|McGraw|Pearson|Wiley|Springer|"
    r"Elsevier|Oxford|Cambridge|Prentice|Tata|Jaico|Housing|"
    r"\bPHI\b|\bEPH\b|\bTMH\b|\bSPD\b|\bBPB\b|ISBN"
    r")[^\n]*",
    re.IGNORECASE,
)

# Accreditation / NBA / NAAC / outcome-table headers
_ACCREDITATION = re.compile(
    r"(?:^|\n)[^\n]*?(?:"
    r"NBA|NAAC|Accreditat|Programme Outcome|PO\d+\s*:|Bloom.{0,20}Level|"
    r"Attainment|Mapping.*CO|CO.*Mapping|CO-PO|PO-CO"
    r")[^\n]*",
    re.IGNORECASE,
)

# University header/footer noise (page numbers, institution names)
_HEADER_FOOTER = re.compile(
    r"(?:^|\n)\s*(?:Page\s*:\s*\d+[^\n]*|"
    r"[^\n]*?(?:University\s*of\s*Technology|Maulana|Formerly\s*West\s*Bengal|"
    r"Syllabus\s*and\s*Curricular\s*Mapping)[^\n]*)",
    re.IGNORECASE,
)

# Teaching scheme / marks / credit metadata lines
_META_LINES = re.compile(
    r"(?:^|\n)[^\n]*?(?:"
    r"Teaching\s*Scheme|Examination\s*Scheme|Maximum\s*Marks|Credit\s*Points?|"
    r"Mid\s*Semester|End\s*Semester\s*Exam|Hrs/Unit|Marks/Unit|"
    r"Theory:\s*\d+|Tutorial:\s*\d+|Practical:\s*(?:NIL|\d+)|"
    r"Duration:\s*\d+|Internal\s*Assessment"
    r")[^\n]*",
    re.IGNORECASE,
)

# Lecture-hour markers like [3L], [10], [2 L]
_LECTURE_HOURS = re.compile(r"\[\s*\d+\s*L?\s*\]", re.IGNORECASE)


def _pre_clean(text: str) -> str:
    """Remove noise sections that should never be embedded."""
    text = text.replace("\r", "")
    text = _MATRIX_ROW.sub("", text)
    text = _BIBLIO_LINE.sub("", text)
    text = _ACCREDITATION.sub("", text)
    text = _HEADER_FOOTER.sub("", text)
    text = _META_LINES.sub("", text)
    text = _LECTURE_HOURS.sub("", text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════════
# STRUCTURAL PATTERN MATCHERS
# ═══════════════════════════════════════════════════════════════════

# Department — "Department of Information Technology", "Dept of CSE"
_DEPT_RE = re.compile(
    r"(?:^|\n)\s*(?:Department|Dept\.?)\s*(?:of\s*)?([A-Za-z\s&/]+?)(?=\n|$)",
    re.IGNORECASE,
)

# Semester — "SEMESTER - VIII", "Sem: 4", "SEMESTER IV", "5th Semester"
_SEM_RE = re.compile(
    r"(?:^|\n)\s*(?:SEMESTER|SEM)\s*[-–:—]?\s*([IVXLC]+|\d+|"
    r"One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)"
    r"(?:\s*(?:Semester|Sem))?(?=\n|\s|$)",
    re.IGNORECASE,
)

_SEM_ORDINAL_RE = re.compile(
    r"(?:^|\n)\s*(\d+)(?:st|nd|rd|th)\s*Semester(?=\n|\s|$)",
    re.IGNORECASE,
)

# Subject code — widest possible coverage
# Matches: "Course Code: PEC-IT801B", "Code: CS6501", "Paper Code: IT-401"
_CODE_RE = re.compile(
    r"(?:^|\n)\s*(?:Course\s*Code|Subject\s*Code|Paper\s*Code|Code)\s*[:\-]\s*"
    r"([A-Za-z0-9][A-Za-z0-9\-]{1,15})",
    re.IGNORECASE,
)

# Subject name — "Course Name: ...", "Subject Name: ...", "Paper Title: ..."
_NAME_RE = re.compile(
    r"(?:Course|Subject|Paper)\s*(?:Name|Title)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)

# Elective type detection (from code prefix or surrounding keywords)
_ELECTIVE_PATTERNS = {
    "PEC": re.compile(r"\bP(?:rofessional\s*)?E(?:lective)?\s*C(?:ourse)?\b|\bPEC\b", re.IGNORECASE),
    "OEC": re.compile(r"\bO(?:pen)?\s*E(?:lective)?\s*C(?:ourse)?\b|\bOEC\b|\bOE\b", re.IGNORECASE),
    "HSS": re.compile(r"\bHumanities?\b|\bSocial\s*Science\b|\bHSS\b", re.IGNORECASE),
    "LAB":  re.compile(r"\bLab(?:oratory)?\b|\bPractical\b", re.IGNORECASE),
    "PROJ": re.compile(r"\bProject\b|\bThesis\b|\bDissertation\b", re.IGNORECASE),
    "CORE": re.compile(r"\bCore\b", re.IGNORECASE),
}

# Module / Unit headings inside a subject block
_MODULE_HEADING = re.compile(
    r"(?:^|\n)\s*(?:Module|Unit|Chapter)\s*[-–:]?\s*(\d+|[IVXLC]+)\b[^\n]*",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════
# STABLE SYLLABUS ID GENERATION
# ═══════════════════════════════════════════════════════════════════

def _dept_abbr(dept: str) -> str:
    """Convert department name to a short abbreviation (≤4 chars)."""
    dept = dept.strip()
    # Already short
    if len(dept) <= 4 and dept.upper() == dept:
        return dept
    # Extract initials if multi-word
    words = re.findall(r"[A-Za-z]+", dept)
    if len(words) >= 2:
        return "".join(w[0] for w in words if w).upper()[:4]
    return dept[:3].upper()


def _sem_to_roman(sem: str) -> str:
    """Normalise semester to Roman numeral string."""
    sem = sem.strip().upper()
    # Already roman
    if re.fullmatch(r"[IVXLC]+", sem):
        return sem
    # Arabic number
    if re.fullmatch(r"\d+", sem):
        arabic = int(sem)
        vals = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),
                (90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),
                (5,"V"),(4,"IV"),(1,"I")]
        result = ""
        for value, numeral in vals:
            while arabic >= value:
                result += numeral
                arabic -= value
        return result
    # Word form
    words = {"ONE":"I","TWO":"II","THREE":"III","FOUR":"IV","FIVE":"V",
             "SIX":"VI","SEVEN":"VII","EIGHT":"VIII","NINE":"IX","TEN":"X"}
    return words.get(sem, sem[:3])


def _make_syllabus_id(dept: str, sem: str, elective_type: str, code: str) -> str:
    """
    Generate a stable, deterministic syllabus ID.
    Preferred Format: {DEPT}-{SEM_ROMAN}-{CODE}
    Example: IT-VIII-IT801B or IT-VIII-PEC-IT801B
    Falls back to a short hash with elective type if code is unavailable.
    """
    d = _dept_abbr(dept) if dept else "GEN"
    s = _sem_to_roman(sem) if sem else "?"
    e = (elective_type or "CORE").upper()
    
    if code:
        c = re.sub(r"[^A-Z0-9\-]", "", code.upper())
        # Include elective type if it's not CORE and not already part of the code
        if e != "CORE" and e not in c:
            return f"{d}-{s}-{e}-{c}"
        return f"{d}-{s}-{c}"
    else:
        # Deterministic hash of dept+sem+elective_type
        raw = f"{d}-{s}-{e}"
        c = hashlib.md5(raw.encode()).hexdigest()[:6].upper()
        return f"{d}-{s}-{e}-{c}"


# ═══════════════════════════════════════════════════════════════════
# ELECTIVE TYPE DETECTOR
# ═══════════════════════════════════════════════════════════════════

def _detect_elective_type(code: str, surrounding_text: str) -> str:
    """
    Infer elective type from the subject code prefix or surrounding keywords.
    Returns one of: PEC, OEC, HSS, LAB, PROJ, CORE.
    """
    combined = f"{code or ''} {surrounding_text}"
    
    # Code prefix hints (e.g., "PEC-IT801B" → PEC)
    if code:
        prefix = re.match(r"^([A-Z]+)", code.upper())
        if prefix:
            pfx = prefix.group(1)
            if pfx in ("PEC",): return "PEC"
            if pfx in ("OEC", "OE"): return "OEC"
            if pfx in ("HSS",): return "HSS"
    
    # Keyword scan
    for etype, pattern in _ELECTIVE_PATTERNS.items():
        if pattern.search(combined):
            return etype
    
    return "CORE"


# ═══════════════════════════════════════════════════════════════════
# MODULE EXTRACTOR
# ═══════════════════════════════════════════════════════════════════

def _extract_modules(block_text: str) -> list:
    """
    Extract module/unit titles from a syllabus block.
    Returns a list of module label strings.
    """
    modules = []
    for m in _MODULE_HEADING.finditer(block_text):
        line = m.group(0).strip()
        # Limit length
        modules.append(line[:80])
    return modules[:10]  # cap at 10 modules


# ═══════════════════════════════════════════════════════════════════
# MAIN SEGMENTER
# ═══════════════════════════════════════════════════════════════════

def segment_curriculum(text: str) -> list:
    """
    Dynamically segments a large curriculum PDF text into hierarchical blocks.
    
    Returns a list of dicts:
    [
        {
            "syllabus_id":   str,   # stable deterministic ID
            "department":    str,
            "semester":      str,
            "subject_name":  str,
            "subject_code":  str,
            "elective_type": str,   # CORE / PEC / OEC / HSS / LAB / PROJ
            "modules":       [str], # list of unit/module headers detected inside
            "syllabus_text": str,   # cleaned text for this subject only
        }, ...
    ]
    
    If no structure is detected, returns an empty list (caller falls back to
    single-syllabus ingestion).
    
    IMPORTANT:
    - Does NOT embed. Returns metadata only.
    - Does NOT hardcode any department, semester, or subject names.
    - Works for IT, CSE, ECE, ME, MBA, and any future curriculum.
    """
    print(f"[Curriculum Parser] Input text length: {len(text)} chars")
    
    # Step 1: pre-clean noise
    text = _pre_clean(text)
    
    segments = []
    
    # ── State tracking ──────────────────────────────────────────────
    current_dept = ""
    current_sem  = ""
    
    current_subject_code  = None
    current_subject_name  = None
    current_block_lines   = []
    buffer_for_name       = []   # rolling 6-line window to guess subject name
    
    # ── Utility: finalise one subject block ─────────────────────────
    def finalise_segment():
        nonlocal current_block_lines, current_subject_code, current_subject_name
        if current_subject_code and current_block_lines:
            block_text = "\n".join(current_block_lines).strip()
            if len(block_text) < 50:  # skip trivially small blocks
                current_block_lines = []
                current_subject_code = None
                current_subject_name = None
                return
            
            el_type = _detect_elective_type(current_subject_code, block_text[:300])
            sid = _make_syllabus_id(current_dept, current_sem, el_type, current_subject_code)
            mods = _extract_modules(block_text)
            
            segments.append({
                "syllabus_id":   sid,
                "department":    current_dept.strip(),
                "semester":      current_sem.strip(),
                "subject_code":  current_subject_code.strip(),
                "subject_name":  (current_subject_name or "Unknown Subject").strip(),
                "elective_type": el_type,
                "modules":       mods,
                "syllabus_text": block_text,
            })
            print(f"[Curriculum Parser]   → Segment: {sid} | {current_subject_name}")
        
        current_block_lines  = []
        current_subject_code = None
        current_subject_name = None

    # ── Line-by-line pass ──────────────────────────────────────────
    lines = text.split("\n")
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (but still accumulate blank separators)
        if not stripped:
            if current_block_lines:
                current_block_lines.append(line)
            continue
        
        # 1. Department detection
        dept_m = _DEPT_RE.search(line)
        if dept_m:
            candidate = dept_m.group(1).strip()
            # Sanity: must be 3–60 chars and contain at least one alpha word
            if 3 <= len(candidate) <= 60 and re.search(r"[A-Za-z]{2}", candidate):
                current_dept = candidate
                print(f"[Curriculum Parser] Department: {current_dept}")
                current_block_lines.append(line)
                buffer_for_name.clear()
                continue
        
        # 2. Semester detection
        sem_m = _SEM_RE.search(line)
        if not sem_m:
            sem_m = _SEM_ORDINAL_RE.search(line)
        if sem_m:
            candidate = sem_m.group(1).strip()
            if len(candidate) <= 10:
                current_sem = candidate
                print(f"[Curriculum Parser] Semester: {current_sem}")
                current_block_lines.append(line)
                buffer_for_name.clear()
                continue
        
        # 3. Subject code detection (boundary of a new subject block)
        code_m = _CODE_RE.search(line)
        if code_m:
            new_code = code_m.group(1).strip()
            
            # Try to find subject name on the same line
            name_m = _NAME_RE.search(line)
            found_name = None
            if name_m:
                found_name = name_m.group(1).strip()
            else:
                # Look back in the rolling buffer
                for b_line in reversed(buffer_for_name):
                    nm = _NAME_RE.search(b_line)
                    if nm:
                        found_name = nm.group(1).strip()
                        break
                # Fallback: last non-meta line in buffer
                if not found_name:
                    for b_line in reversed(buffer_for_name):
                        if not re.search(
                            r"credit|contact|l[\-–]t[\-–]p|hour|mark|scheme|code",
                            b_line, re.IGNORECASE
                        ):
                            cand = b_line.strip()
                            if len(cand) >= 4:
                                found_name = cand
                                break
            
            # Finalise previous segment, start a new one
            finalise_segment()
            current_subject_code = new_code
            current_subject_name = found_name
            current_block_lines  = []
            
            if found_name:
                current_block_lines.append(f"Subject Name: {found_name}")
            current_block_lines.append(line)
            buffer_for_name.clear()
            continue
        
        # 4. Accumulate line
        current_block_lines.append(line)
        buffer_for_name.append(stripped)
        if len(buffer_for_name) > 6:
            buffer_for_name.pop(0)
    
    # Finalise the last block
    finalise_segment()
    
    print(f"[Curriculum Parser] Total subjects detected: {len(segments)}")
    return segments
