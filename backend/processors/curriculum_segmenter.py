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
# METADATA INFERENCE HEURISTICS
# ═══════════════════════════════════════════════════════════════════

def _infer_semester_from_code(code: str) -> str:
    """
    Heuristic: Extract the first digit of the numeric sequence in the code.
    Example: CS301 -> 3, IT801B -> 8, MA101 -> 1
    Returns Roman numeral string if found, else None.
    """
    if not code:
        return None
    # Find the first digit in the code
    match = re.search(r"(\d)", code)
    if match:
        digit = match.group(1)
        return _sem_to_roman(digit)
    return None


def _extract_subject_owner(code: str) -> str:
    """
    Extract the alphabetic prefix of the course code.
    Example: CH201 -> CH, EE301 -> EE
    """
    if not code:
        return None
    # Match leading uppercase letters
    match = re.match(r"^([A-Z]+)", code.upper())
    if match:
        return match.group(1)
    return None


def _calculate_metadata_confidence(detected_sem: str, inferred_sem: str) -> float:
    """
    Calculate confidence based on agreement between explicit heading and code heuristic.
    """
    if not detected_sem or not inferred_sem:
        return 0.70 # Baseline
    
    # Normalise both to roman
    d_sem = _sem_to_roman(detected_sem)
    i_sem = _sem_to_roman(inferred_sem)
    
    if d_sem == i_sem:
        return 0.95
    return 0.60 # Disagreement penalty


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
    sem = str(sem).strip().upper()
    # Already roman
    if re.fullmatch(r"[IVXLC]+", sem):
        return sem
    # Arabic number
    if re.fullmatch(r"\d+", sem):
        arabic = int(sem)
        if arabic == 0: return "?"
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


def _make_syllabus_id(curr_dept: str, sem: str, elective_type: str, code: str) -> str:
    """
    Generate a stable, deterministic syllabus ID based on CURRICULUM CONTEXT.
    """
    d = _dept_abbr(curr_dept) if curr_dept else "GEN"
    s = _sem_to_roman(sem) if sem else "?"
    e = (elective_type or "CORE").upper()
    
    if code:
        c = re.sub(r"[^A-Z0-9\-]", "", code.upper())
        if e != "CORE" and e not in c:
            return f"{d}-{s}-{e}-{c}"
        return f"{d}-{s}-{c}"
    else:
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

# ═══════════════════════════════════════════════════════════════════
# STATE-BASED HIERARCHICAL PARSER
# ═══════════════════════════════════════════════════════════════════

def segment_curriculum(text: str) -> list:
    """
    Overhauled state-based curriculum parser.
    Levels: Global Context → Semester Context → Subject Context
    """
    print(f"[Curriculum Parser] Input text length: {len(text)} chars")
    
    # Step 1: pre-clean noise
    text = _pre_clean(text)
    lines = [l.strip() for l in text.split("\n")]
    
    segments = []
    
    # ── Level 1: Global Context Extraction ──────────────────────────
    global_program = "Unknown Program"
    global_dept = "Department Unknown"
    
    # Scan first 150 lines for global context
    for i in range(min(150, len(lines))):
        line = lines[i]
        if not line: continue
        
        # Detect Program (e.g. B.Tech)
        prog_m = re.search(r"\b(B\.?\s*Tech|M\.?\s*Tech|BCA|MCA|MBA|B\.?\s*Sc)\b", line, re.IGNORECASE)
        if prog_m:
            global_program = prog_m.group(1).strip()
            
        # Detect Global Dept (e.g. Information Technology)
        # We look for "Syllabus for...", "Department of...", "B.Tech in..."
        # We handle: "B.Tech in Information Technology", "Dept of CSE", "B.Tech (IT)"
        dept_match = re.search(r"(?:for|of|in|Dept\.?\s*of)\s+\(?([A-Za-z\s&/]{2,60})\)?", line, re.IGNORECASE)
        if dept_match:
            cand = dept_match.group(1).strip()
            
            # Clean up: remove Program names from the start of the department string
            # e.g. "B. Tech in Information Technology" -> "Information Technology"
            cand = re.sub(r"^(?:B\.?\s*Tech|M\.?\s*Tech|BCA|MCA|MBA|B\.?\s*Sc|M\.?\s*Sc)\s+(?:in|of|for|—|-)\s+", "", cand, flags=re.IGNORECASE)
            
            # Filter out known non-department noise
            noise_words = ["semester", "session", "university of", "formerly", "technology university", "west bengal", "maulana", "syllabi", "curriculum"]
            if not any(noise in cand.lower() for noise in noise_words):
                # Sanity: must be long enough and contain more than just 'Technology' or 'Engineering'
                if len(cand) >= 2 and cand.lower() not in ["technology", "engineering", "science"]:
                    # If we already have a value, only overwrite if this line looks "stronger" (e.g. starts with Dept)
                    if global_dept == "Department Unknown" or "dept" in line.lower():
                        global_dept = cand
                        print(f"[Curriculum Parser]   -> Identified Dept: {global_dept}")

    print(f"[Curriculum Parser] Global Context: {global_program} | {global_dept}")

    # ── Level 2 & 3: State-based Iteration ──────────────────────────
    
    # State variables
    current_semester = "Unknown"
    current_subject_name = None
    current_subject_code = None
    current_block_lines = []
    reference_mode = False
    
    # Boundary logic: candidate for subject name
    candidate_name = None
    
    def finalise_subject():
        nonlocal current_subject_name, current_subject_code, current_block_lines
        if current_subject_name and current_subject_code and current_block_lines:
            block_text = "\n".join(current_block_lines).strip()
            if len(block_text) < 100: return # Skip ghosts
            
            el_type = _detect_elective_type(current_subject_code, block_text[:400])
            inferred_sem = _infer_semester_from_code(current_subject_code)
            final_sem = current_semester if current_semester != "Unknown" else (inferred_sem or "Unknown")
            
            # Inherit Global Context
            subject_owner = _extract_subject_owner(current_subject_code)
            sid = _make_syllabus_id(global_dept, final_sem, el_type, current_subject_code)
            
            segments.append({
                "syllabus_id":           sid,
                "curriculum_department": global_dept,
                "subject_owner_department": subject_owner,
                "program":               global_program,
                "semester":              _sem_to_roman(final_sem),
                "subject_code":          current_subject_code,
                "subject_name":          current_subject_name,
                "elective_type":         el_type,
                "metadata_confidence":   _calculate_metadata_confidence(current_semester, inferred_sem),
                "modules":               _extract_modules(block_text),
                "syllabus_text":         block_text,
                "department":            global_dept # legacy
            })
            print(f"[Curriculum Parser] -> Found: {sid} | {current_subject_name}")
            
        current_subject_name = None
        current_subject_code = None
        current_block_lines = []
        reference_mode = False

    # Regex for detecting the start of a references section
    _REF_HEADING_RE = re.compile(
        r"^(?:\d+\.?\s*)?(?:Text\s*books?|References?|Reference\s*books?|Suggested\s*Readings?|Bibliography)(?:\s*and\s*reference\s*books?)?\s*:?",
        re.IGNORECASE
    )

    # Metadata exclusion list (never treat as subject names)
    EXCLUSIONS = {
        "course name", "subject name", "course code", "subject code", "paper code", "paper name",
        "name of the course", "name of the paper", "contacts", "credit", "objective", "outcome", 
        "references", "text book", "reference book", "teaching scheme", "examination scheme",
        "syllabus for", "department of", "session", "semester", "ltp", "l-t-p"
    }

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped: continue
        
        # 1. Semester Detection (Level 2)
        sem_m = _SEM_RE.search(stripped) or _SEM_ORDINAL_RE.search(stripped)
        if sem_m:
            candidate_sem = sem_m.group(1).strip()
            if len(candidate_sem) < 10:
                current_semester = candidate_sem
                reference_mode = False # Reset on new semester
                print(f"[Curriculum Parser] Entering Semester: {current_semester}")
                continue

        # 2. Subject Code Detection (Subject Boundary Start)
        code_m = _CODE_RE.search(stripped)
        if code_m:
            new_code = code_m.group(1).strip()
            
            # A valid code MUST be preceded by a standalone title line (candidate_name)
            # OR the line itself must have a name (only if NOT metadata)
            name_in_line = _NAME_RE.search(stripped)
            is_metadata_line = any(ex in stripped.lower() for ex in EXCLUSIONS)
            
            if name_in_line and not is_metadata_line:
                # Subject header is on one line: e.g. "Computer Networks (CS601)"
                # But if it starts with "Name of the Course:", we usually want to ignore it 
                # as a boundary unless no candidate_name exists.
                finalise_subject()
                current_subject_name = name_in_line.group(1).strip()
                current_subject_code = new_code
                current_block_lines = [stripped]
                candidate_name = None
                reference_mode = False # Reset on new subject
                continue
            elif candidate_name:
                # Standard format: 
                # [Line i-1] Cryptography and Network Security
                # [Line i]   Code: IT801B
                finalise_subject()
                current_subject_name = candidate_name
                current_subject_code = new_code
                current_block_lines = [f"Subject Name: {candidate_name}", stripped]
                candidate_name = None
                reference_mode = False # Reset on new subject
                continue
            else:
                # Code found but no candidate name above it? 
                if current_subject_code:
                    current_block_lines.append(stripped)
                continue

        # 3. Candidate Name logic
        is_metadata = any(ex in stripped.lower() for ex in EXCLUSIONS)
        # A line is a candidate name if it's short, not metadata, and doesn't look like a value/code
        if 4 <= len(stripped) <= 80 and not is_metadata and not stripped.endswith(":") and not re.search(r"\d{2,}", stripped):
            candidate_name = stripped
        elif is_metadata:
            # Reset candidate if we hit metadata - a standalone title shouldn't be separated by "Credit: 4"
            candidate_name = None
        else:
            # For other lines (long text, units), we keep the candidate for 1 line only
            # to handle cases where there's a small gap, but generally we want it close.
            pass

        # 4. Reference Mode Detection
        if _REF_HEADING_RE.match(stripped):
            reference_mode = True
            continue

        # 5. Accumulate content
        if current_subject_code and not reference_mode:
            # Check for "STOP" keywords that indicate the end of useful content 
            # (e.g. next subject header or footer)
            current_block_lines.append(stripped)

    # Finalise last subject
    finalise_subject()
    
    print(f"[Curriculum Parser] Total subjects detected: {len(segments)}")
    return segments
