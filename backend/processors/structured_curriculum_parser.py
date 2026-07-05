"""
processors/structured_curriculum_parser.py
--------------------------------------------
Structured Curriculum Parser.

Originally designed for AICTE, but named and architected generally to support
future university templates (MAKAUT, VTU, AKTU, etc.).

Features:
  - Document format detection using indicator scoring.
  - Line-by-line state machine parser (no coarse regex splits).
  - Structured CO-PO mapping dictionary parser.
  - Separate units/modules array parser.
  - Ingestion-time Bloom taxonomy classification for Course Outcomes.
  - Parser confidence score and targeted structural warnings.
  - Preserved raw text block and parsed JSON blocks.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from services.bloom_classifier import classify_bloom

# Helper imports from segmenter (resolved dynamically to avoid circular import)
def _get_segmenter_helpers():
    from processors.curriculum_segmenter import (
        _sem_to_roman,
        _infer_semester_from_code,
        _extract_subject_owner,
        _detect_elective_type,
        _make_syllabus_id
    )
    return _sem_to_roman, _infer_semester_from_code, _extract_subject_owner, _detect_elective_type, _make_syllabus_id


# ═══════════════════════════════════════════════════════════════════
# DOCUMENT FORMAT DETECTOR
# ═══════════════════════════════════════════════════════════════════

def detect_document_format(text: str) -> str:
    """
    Score the document to detect if it is a Structured Curriculum (AICTE)
    or a legacy single-subject syllabus.
    """
    score_aicte = 0
    
    indicators = [
        "Course Outcomes",
        "CO-PO Mapping",
        "Course Objectives",
        "Course Title",
        "Program Outcomes",
        "PSO",
        "Syllabus and Curricular Mapping"
    ]
    
    for ind in indicators:
        if ind.lower() in text.lower():
            score_aicte += 1
            
    if score_aicte >= 3:
        return "AICTE"
        
    if "Course Code" in text or "Subject Code" in text or "Paper Code" in text:
        return "SINGLE"
        
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# METADATA DERIVATION
# ═══════════════════════════════════════════════════════════════════

def derive_department(text: str, course_code: str) -> str:
    """
    Derive the department name from structural context:
    1. Extract from "B.Tech in [Department]" or similar program string.
    2. Extract and expand from the course code prefix/infix (e.g. PEC-IT801B -> IT -> Information Technology).
    """
    # 1. B.Tech in ... or similar
    match = re.search(
        r"\b(?:B\.?\s*Tech(?:\.?\s*in)?|M\.?\s*Tech(?:\.?\s*in)?|BCA\s+in|MCA\s+in|MBA\s+in)\s+([A-Za-z\s&/]{3,50})",
        text,
        re.IGNORECASE
    )
    if match:
        dept = match.group(1).strip()
        # Clean trailing section/session markers
        dept = re.split(r"\b(?:Syllabus|Curriculum|Semester|Year|Session)\b", dept, flags=re.IGNORECASE)[0].strip()
        return dept
        
    # 2. Course code check
    if course_code:
        parts = re.split(r"[^A-Za-z]", course_code)
        for part in parts:
            abbr = part.upper()
            if abbr in ["IT", "CS", "CSE", "EE", "ECE", "ME", "CE", "MCA", "BCA", "MBA"]:
                mapping = {
                    "IT": "Information Technology",
                    "CS": "Computer Science and Engineering",
                    "CSE": "Computer Science and Engineering",
                    "EE": "Electrical Engineering",
                    "ECE": "Electronics and Communication Engineering",
                    "ME": "Mechanical Engineering",
                    "CE": "Civil Engineering"
                }
                return mapping.get(abbr, abbr)
                
        # Substring/prefix fallback
        code_clean = re.sub(r"^PEC-|^OEC-|^HSS-", "", course_code, flags=re.IGNORECASE)
        prefix_match = re.match(r"^([A-Z]+)", code_clean.upper())
        if prefix_match:
            abbr = prefix_match.group(1)
            mapping = {
                "IT": "Information Technology",
                "CS": "Computer Science and Engineering",
                "CSE": "Computer Science and Engineering",
                "EE": "Electrical Engineering",
                "ECE": "Electronics and Communication Engineering",
                "ME": "Mechanical Engineering",
                "CE": "Civil Engineering"
            }
            return mapping.get(abbr, abbr)
            
    return "Information Technology"


def derive_program(text: str) -> str:
    """
    Extract the program name from:
    "Syllabus and Curricular Mapping for B.Tech in ..."
    or generic fallbacks.
    """
    match = re.search(
        r"Syllabus\s+and\s+Curricular\s+Mapping\s+for\s+([A-Za-z\.\s]+?)\s+in",
        text,
        re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
        
    match_fallback = re.search(r"\b(B\.?\s*Tech|M\.?\s*Tech|BCA|MCA|MBA|B\.?\s*Sc)\b", text, re.IGNORECASE)
    if match_fallback:
        return match_fallback.group(1).strip()
        
    return "B.Tech"


# ═══════════════════════════════════════════════════════════════════
# SECTION AND ELEMENT SUB-PARSERS
# ═══════════════════════════════════════════════════════════════════

def _parse_outcomes_with_bloom(out_text: str) -> List[Dict[str, str]]:
    """Parse outcomes into structured list and classify Bloom levels."""
    outcomes = []
    lines = [l.strip() for l in out_text.split("\n") if l.strip()]
    co_index = 1
    
    for line in lines:
        match_co = re.match(r"^\s*(?:CO\d+|[0-9]+)\s*[:\.]?\s*(.+)", line, re.IGNORECASE)
        if match_co:
            co_id = f"CO{co_index}"
            co_text = match_co.group(1).strip()
        else:
            co_id = f"CO{co_index}"
            co_text = line
            
        co_index += 1
        bloom = classify_bloom(co_text)
        outcomes.append({
            "co":          co_id,
            "text":        co_text,
            "bloom_level": bloom["bloom_level"],
            "difficulty":  bloom["difficulty"]
        })
    return outcomes


def _parse_copo_mapping(map_text: str) -> Dict[str, Dict[str, int]]:
    """Parse mapping lines into a matrix of CO label -> {PO/PSO label -> strength}."""
    mappings = {}
    lines = [l.strip() for l in map_text.split("\n") if l.strip()]
    header_labels = []
    
    for line in lines:
        # Detect Header Line
        if "PO1" in line or "PO-1" in line:
            words = re.findall(r"\b(?:PO\d+|PSO\d+|PO-\d+|PSO-\d+)\b", line, re.IGNORECASE)
            if words:
                header_labels = [w.upper().replace("-", "") for w in words]
                continue
                
        # Parse Mapping Row
        match_row = re.match(r"^\s*(CO\d+|CO)\b(.*)", line, re.IGNORECASE)
        if match_row:
            co_label = match_row.group(1).upper()
            row_data = match_row.group(2).strip()
            cells    = re.split(r"\s+|\|", row_data)
            cells    = [c.strip() for c in cells if c.strip()]
            row_map  = {}
            
            for idx, cell in enumerate(cells):
                try:
                    val = int(cell)
                    label = header_labels[idx] if header_labels and idx < len(header_labels) else f"PO{idx+1}"
                    row_map[label] = val
                except ValueError:
                    pass
                    
            if row_map:
                if co_label == "CO":
                    co_label = f"CO{len(mappings) + 1}"
                mappings[co_label] = row_map
                
    # Fallback to pure matrix parser if no CO headings matched but numbers exist
    if not mappings:
        co_index = 1
        for line in lines:
            numbers = re.findall(r"\b[123]\b", line)
            if len(numbers) >= 3:
                row_map = {f"PO{idx+1}": int(num) for idx, num in enumerate(numbers)}
                mappings[f"CO{co_index}"] = row_map
                co_index += 1
                
    return mappings


def _parse_units_separately(units_lines: List[str]) -> List[Dict[str, Any]]:
    """Split lines in the syllabus section into distinct units with titles and content."""
    units = []
    current_unit = None
    _UNIT_HEADER_RE = re.compile(r"^\s*(?:Unit|Module|Chapter)\s*(\d+|[IVXLC]+)\s*[:\-–]?\s*(.*)", re.IGNORECASE)
    
    for line in units_lines:
        match = _UNIT_HEADER_RE.match(line)
        if match:
            if current_unit:
                units.append(current_unit)
            unit_num   = match.group(1).strip()
            unit_title = match.group(2).strip()
            current_unit = {
                "unit":          unit_num,
                "title":         unit_title if unit_title else f"Unit {unit_num}",
                "content_lines": []
            }
        else:
            if current_unit:
                current_unit["content_lines"].append(line)
            else:
                current_unit = {
                    "unit":          "1",
                    "title":         "Syllabus Content",
                    "content_lines": [line]
                }
                
    if current_unit:
        units.append(current_unit)
        
    return [
        {
            "unit":    u["unit"],
            "title":   u["title"],
            "content": "\n".join(u["content_lines"]).strip()
        }
        for u in units
    ]


# ═══════════════════════════════════════════════════════════════════
# LINE-BY-LINE STATE MACHINE PARSER
# ═══════════════════════════════════════════════════════════════════

def check_trigger(line: str) -> Optional[str]:
    """
    Identifies section transition headers.
    Uses \\s* between words to handle PDF extraction artefacts where spaces
    are stripped (e.g. "CourseTitle:", "CourseOutcomes(COs)").
    """
    l = line.strip()

    # TITLE: "Course Title:", "CourseTitle:", "Course Name:", etc.
    if re.search(r"(?:Course\s*Title|Course\s*Name|Subject\s*Name|Paper\s*Title)\s*[:\-–]", l, re.IGNORECASE):
        return "TITLE"

    # OBJECTIVES: "Course Objectives:", "CourseObjectives:", standalone "Objectives"
    if re.search(r"^Course\s*Objectives?\s*[:\-–]?$", l, re.IGNORECASE) or \
       re.match(r"^Objectives?\s*[:\-–]?$", l, re.IGNORECASE) or \
       re.search(r"COURSE\s*OBJECTIVE\s*[:\-–]?", l, re.IGNORECASE):
        return "OBJECTIVES"

    # OUTCOMES: "Course Outcomes:", "CourseOutcomes:", "COURSE OUTCOMES (COs)", etc.
    if re.search(r"Course\s*Outcomes?\s*(?:\([^)]*\))?\s*[:\-–]?$", l, re.IGNORECASE) or \
       re.match(r"^Outcomes?\s*[:\-–]?$", l, re.IGNORECASE) or \
       re.search(r"COURSE\s*OUTCOMES?\s*\(?COs?\)?", l, re.IGNORECASE):
        return "OUTCOMES"

    # MAPPING: "CO-PO Mapping", "Mapping of COs with POs", "Course Articulation Matrix"
    if re.search(r"CO\s*-?\s*PO\s*Mapping", l, re.IGNORECASE) or \
       re.search(r"Mapping\s*of\s*COs", l, re.IGNORECASE) or \
       re.search(r"Course\s*Articulation\s*Matrix", l, re.IGNORECASE) or \
       re.search(r"CO\s*-?\s*PO\s*Correlation", l, re.IGNORECASE) or \
       re.search(r"Correlation\s*Matrix", l, re.IGNORECASE):
        return "MAPPING"

    # SYLLABUS: standalone "Units", "Syllabus", "Modules" or "University Syllabus:"
    if re.match(r"^(?:Units?|Syllabus|Modules?)\s*[:\-–]?$", l, re.IGNORECASE) or \
       re.search(r"University\s*Syllabus\s*[:\-–]", l, re.IGNORECASE):
        return "SYLLABUS"

    # REFERENCES: "References", "Reference Books", "Text Books", etc.
    if re.match(r"^(?:References?|Reference\s*Books?|Text\s*Books?|Textbooks?|Suggested\s*Readings?|Bibliography|Resources?)\s*[:\-–]?$", l, re.IGNORECASE):
        return "REFERENCES"

    return None


def clean_inline_content(line: str, trigger_name: str) -> str:
    """Removes the trigger keyword and clean trailing prefix punctuation."""
    cleaned = re.sub(
        r"^\s*(?:Course\s*Objectives?|Objectives?|Course\s*Outcomes?|Outcomes?|CO-PO\s*Mapping|CO\s*PO\s*Mapping|CO-PO\s*Correlation|Units|Unit|Modules|Module|Syllabus|References?|Suggested\s*Readings?|Bibliography)",
        "",
        line,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"^[:\-–\s]+", "", cleaned)
    return cleaned.strip()


def parse_aicte_curriculum(text: str) -> List[Dict[str, Any]]:
    """
    State-machine structured parser for AICTE curriculums.
    Resolves lines sequentially to extract deep hierarchical structures.
    """
    _sem_to_roman, _infer_semester_from_code, _extract_subject_owner, _detect_elective_type, _make_syllabus_id = _get_segmenter_helpers()

    lines = text.split("\n")
    courses = []
    
    # State tracking variables for the current course
    current_course = None
    raw_lines = []
    
    # Section content accumulators
    objectives_lines = []
    outcomes_lines = []
    mapping_lines = []
    units_lines = []
    references_lines = []
    
    state = "WAITING"
    
    _COURSE_TITLE_RE = re.compile(
        r"^\s*(?:Course\s*Title|Course\s*Name|Subject\s*Name|Paper\s*Title)\s*[:\-–]\s*(.*)",
        re.IGNORECASE
    )
    
    def finalize_current_course():
        nonlocal current_course, objectives_lines, outcomes_lines, mapping_lines, units_lines, references_lines, raw_lines
        if not current_course:
            return
            
        obj_text = "\n".join(objectives_lines).strip()
        out_text = "\n".join(outcomes_lines).strip()
        map_text = "\n".join(mapping_lines).strip()
        ref_text = "\n".join(references_lines).strip()
        
        # Parse fields
        units    = _parse_units_separately(units_lines)
        outcomes = _parse_outcomes_with_bloom(out_text)
        co_po    = _parse_copo_mapping(map_text)
        
        # Warnings
        warnings = []
        if not outcomes:
            warnings.append("⚠ Course Outcomes not found")
        if not co_po:
            warnings.append("⚠ CO-PO table not found")
        if not current_course["semester"]:
            warnings.append("⚠ Semester not explicitly found")
        if not ref_text:
            warnings.append("⚠ References missing")
            
        # Inferred Semester fallback
        if not current_course["semester"] and current_course["code"]:
            inferred_sem = _infer_semester_from_code(current_course["code"])
            if inferred_sem:
                current_course["semester"] = inferred_sem
                warnings.append("⚠ Semester inferred from code")
                
        # Resolve Roman semester
        sem_roman = _sem_to_roman(current_course["semester"]) if current_course["semester"] else "Unknown"
        
        raw_block_text = "\n".join(raw_lines).strip()
        dept       = derive_department(raw_block_text, current_course["code"])
        prog       = derive_program(raw_block_text)
        owner_dept = _extract_subject_owner(current_course["code"])
        el_type    = _detect_elective_type(current_course["code"], raw_block_text[:1000])
        
        # Build Syllabus ID
        sid = _make_syllabus_id(dept, sem_roman, el_type, current_course["code"])
        
        # Compile module titles list
        module_titles = [u["title"] for u in units if u.get("title")]
        if not module_titles:
            module_titles = [f"Unit {u['unit']}" for u in units]
            
        parsed_data = {
            "course_title":      current_course["title"],
            "course_code":       current_course["code"],
            "semester":          sem_roman,
            "course_objectives": obj_text,
            "course_outcomes":   outcomes,
            "co_po_mapping":     co_po,
            "units":             units,
            "references":        ref_text
        }
        
        # Log metadata details to console as requested
        print("Detected Course:")
        print(current_course["title"])
        print("Code:")
        print(current_course["code"])
        print("Semester:")
        print(sem_roman)
        print("Detected CO count:")
        print(len(outcomes))
        print("Detected PO mappings:")
        print(len(co_po))
        
        courses.append({
            "syllabus_id":              sid,
            "curriculum_department":    dept,
            "subject_owner_department": owner_dept,
            "program":                  prog,
            "semester":                 sem_roman,
            "subject_code":             current_course["code"],
            "subject_name":             current_course["title"],
            "elective_type":            el_type,
            "metadata_confidence":      0.95,
            "modules":                  module_titles,
            "syllabus_text":            raw_block_text,
            "text":                     raw_block_text,
            "department":               dept,
            "parser":                   "AICTE",
            "parser_confidence":        0.97,
            "warnings":                 warnings,
            "raw_text":                 raw_block_text,
            "parsed":                   parsed_data,
            "parser_metadata": {
                "parser":           "AICTE",
                "program":          prog,
                "department":       dept,
                "semester":         sem_roman,
                "course_code":      current_course["code"],
                "co_count":         len(outcomes),
                "po_mapping_count": len(co_po),
                "module_count":     len(units)
            }
        })
        
        # Clean local accumulators
        objectives_lines.clear()
        outcomes_lines.clear()
        mapping_lines.clear()
        units_lines.clear()
        references_lines.clear()
        raw_lines.clear()

    # Iterate line-by-line
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        trigger = check_trigger(line)
        if trigger:
            if trigger == "TITLE":
                finalize_current_course()
                current_course = {"title": "", "code": "", "semester": ""}
                raw_lines = [line]
                match = _COURSE_TITLE_RE.match(line)
                if match:
                    raw_title = match.group(1).strip()

                    # Many PDFs put title and code on the same line:
                    # "CourseTitle:Cryptography&NetworkSecurity Code:PEC-IT801B"
                    # Strip everything from " Code:" onwards and use it as the code.
                    inline_code = re.search(
                        r"(?:\s+|\b)(?:Code|Course\s*Code|Subject\s*Code)\s*[:\-–]\s*([A-Za-z0-9\-]+)",
                        raw_title, re.IGNORECASE
                    )
                    if inline_code:
                        current_course["code"] = inline_code.group(1).strip()
                        # Remove the code portion from the title
                        raw_title = raw_title[:inline_code.start()].strip()

                    # Also extract inline semester if present
                    inline_sem = re.search(
                        r"\bSemester\s*[:\-–]\s*(\d+(?:st|nd|rd|th)?|[IVXLC]+)",
                        raw_title, re.IGNORECASE
                    )
                    if inline_sem:
                        current_course["semester"] = inline_sem.group(1).strip()
                        raw_title = raw_title[:inline_sem.start()].strip()

                    current_course["title"] = raw_title
                state = "HEADER"
            else:
                if current_course:
                    state = trigger
                    raw_lines.append(line)
                    # Check for inline content in trigger header
                    inline = clean_inline_content(line, trigger)
                    if inline:
                        if trigger == "OBJECTIVES": objectives_lines.append(inline)
                        elif trigger == "OUTCOMES": outcomes_lines.append(inline)
                        elif trigger == "MAPPING": mapping_lines.append(inline)
                        elif trigger == "SYLLABUS": units_lines.append(inline)
                        elif trigger == "REFERENCES": references_lines.append(inline)
            continue
            
        # Accumulate values inside state
        if current_course:
            raw_lines.append(line)
            if state == "HEADER":
                code_match = re.search(r"(?:Course\s*Code|Subject\s*Code|Code)\s*[:\-–]\s*([A-Za-z0-9\-]{2,20})", line, re.IGNORECASE)
                if code_match:
                    current_course["code"] = code_match.group(1).strip()
                sem_match = re.search(r"Semester\s*[:\-–]\s*(\d+(?:st|nd|rd|th)?|[IVXLC]+)", line, re.IGNORECASE)
                if sem_match:
                    current_course["semester"] = sem_match.group(1).strip()
                if not current_course["title"] and not code_match and not sem_match:
                    # Treat the first non-code/non-semester line in header as the title if still empty
                    current_course["title"] = line.strip()
            elif state == "OBJECTIVES":
                objectives_lines.append(line)
            elif state == "OUTCOMES":
                outcomes_lines.append(line)
            elif state == "MAPPING":
                mapping_lines.append(line)
            elif state == "SYLLABUS":
                units_lines.append(line)
            elif state == "REFERENCES":
                references_lines.append(line)

    # Save the last parsed course block
    finalize_current_course()
    
    print(f"[Structured Parser] Ingestion finished. Detected courses: {len(courses)}")
    return courses
