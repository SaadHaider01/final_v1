import re

def chunk_syllabus(text):
    pattern = r"(?=(Module|Unit|Chapter)\s+\d+)"
    splits = re.split(pattern, text, flags=re.IGNORECASE)
    chunks = []

    temp = ""
    for part in splits:
        if re.match(pattern, part, flags=re.IGNORECASE):
            if temp:
                chunks.append(temp.strip())
            temp = part
        else:
            temp += " " + part

    if temp:
        chunks.append(temp.strip())

    return chunks if chunks else [text]
