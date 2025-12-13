import re

def chunk_syllabus(text: str):
    """
    Smart syllabus chunking:
    - Split by module/unit headings
    - Split by bullet points
    - Split long lines into 200-char chunks
    - Clean empty chunks
    """

    chunks = []

    # Normalize
    text = text.replace("\r", "")

    # Step 1 — split by headings like:
    # MODULE 1, Unit – 1, UNIT I, Chapter 1
    sections = re.split(r'\b(?:Module|Unit|Chapter)\s*[\-–:]?\s*\d+\b', text, flags=re.I)

    for sec in sections:
        # Step 2 — split into lines
        lines = [l.strip() for l in sec.split("\n") if l.strip()]

        for line in lines:
            # Step 3 — split bullet lists
            parts = re.split(r'[•·\-–]\s+', line)
            for p in parts:
                if len(p) < 20:
                    continue  # ignore trash or tiny fragments

                # Step 4 — force max chunk size ~ 200 chars
                while len(p) > 220:
                    chunks.append(p[:220])
                    p = p[220:]
                if p.strip():
                    chunks.append(p.strip())

    return chunks
