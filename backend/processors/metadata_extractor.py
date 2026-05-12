import re

def extract_metadata(text: str) -> dict:
    """
    Scans the start of the syllabus text for common academic metadata patterns.
    Returns a dict with found fields.
    """
    metadata = {
        "subject_name": None,
        "subject_code": None,
        "semester":     None,
        "program":      None,
        "department":   None,
        "bos":          None
    }
    
    # Take first 2000 chars for metadata scanning
    head = text[:2000]
    
    patterns = {
        "subject_name": [
            r"Subject\s*Name\s*[:\-]\s*(.+)",
            r"Name\s*of\s*the\s*Subject\s*[:\-]\s*(.+)",
            r"Course\s*Title\s*[:\-]\s*(.+)",
            r"(?:^|\n)([A-Z\s]{5,60})(?:\n|$)" # Fallback: Look for a lone uppercase line
        ],
        "subject_code": [
            r"Subject\s*Code\s*[:\-]\s*([\w\-\/]+)",
            r"Paper\s*Code\s*[:\-]\s*([\w\-\/]+)",
            r"Code\s*[:\-]\s*([\w\-\/]+)"
        ],
        "semester": [
            r"Semester\s*[:\-]\s*(\d+|[IVXLC]+)",
            r"([\d\w]+)\s*Semester"
        ],
        "program": [
            r"Program\s*[:\-]\s*(.+)",
            r"Course\s*[:\-]\s*(B\.Tech|M\.Tech|BCA|MCA|BBA|MBA|B\.Sc|M\.Sc)"
        ],
        "department": [
            r"Department\s*[:\-]\s*(.+)",
            r"Dept\.\s*[:\-]\s*(.+)"
        ],
        "bos": [
            r"Board\s*of\s*Studies\s*[:\-]\s*(.+)",
            r"BOS\s*[:\-]\s*(.+)"
        ]
    }
    
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, head, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                # Clean up value (remove trailing colons, whitespace)
                val = re.sub(r"[:\-]$", "", val).strip()
                if val:
                    metadata[key] = val
                    break
                    
    return metadata
