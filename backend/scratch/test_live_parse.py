import sys
sys.path.insert(0, ".")
from processors.document_router import detect_document_type
from processors.curriculum_splitter import split_into_course_blocks
from processors.structured_curriculum_parser import parse_aicte_curriculum

with open("scratch/last_uploaded_text.txt", "r", encoding="utf-8") as f:
    text = f.read()

doc_type = detect_document_type(text, source="PDF")
print("Type:", doc_type)

blocks = split_into_course_blocks(text)
print(f"Blocks: {len(blocks)}")

for i, block in enumerate(blocks):
    result = parse_aicte_curriculum(block)
    if result:
        c = result[0]
        title = c["subject_name"]
        code = c["subject_code"]
        sem = c["semester"]
        dept = c["department"]
        sid = c["syllabus_id"]
        warns = c["warnings"]
        parsed = c.get("parsed", {})
        cos = len(parsed.get("course_outcomes", []))
        copo = len(parsed.get("co_po_mapping", {}))
        units = len(parsed.get("units", []))
        print(f"--- Course {i+1} ---")
        print(f"  Title:    {title}")
        print(f"  Code:     {code}")
        print(f"  Semester: {sem}")
        print(f"  Dept:     {dept}")
        print(f"  SID:      {sid}")
        print(f"  Warnings: {warns}")
        print(f"  COs:      {cos}")
        print(f"  CO-PO rows: {copo}")
        print(f"  Units:    {units}")
    else:
        print(f"--- Course {i+1}: EMPTY RESULT ---")
