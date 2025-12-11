from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import re


from models.embedder import Embedder
from processors.pdf_reader import extract_text_from_pdf
from processors.text_chunker import chunk_syllabus
from vectorstores.chroma_store import VectorStore  # or chroma_Store if that's the filename

app = Flask(__name__)
CORS(app)

embedder = Embedder()
vector_db = VectorStore(embed_fn=embedder.embed)

SYLLABI = {}
SYLLABUS_CHUNKS = {}  # optional: to keep chunks per syllabus


# 🔹 Ingest Syllabus (frontend calls: /ingest_syllabus)
@app.route("/ingest_syllabus", methods=["POST"])
def ingest_syllabus():
    mode = request.form.get("mode", "pdf")
    syllabus_id = str(uuid.uuid4())

    if mode == "pdf":
        if "file" not in request.files:
            return jsonify({"error": "No PDF uploaded"}), 400
        pdf = request.files["file"]
        text = extract_text_from_pdf(pdf)
    else:
        text = request.form.get("text", "")
        if not text.strip():
            return jsonify({"error": "Empty syllabus text"}), 400

    chunks = chunk_syllabus(text)

    # store in vector DB
    vector_db.add_syllabus(syllabus_id, chunks)
    SYLLABUS_CHUNKS[syllabus_id] = chunks

    metadata = {
        "syllabus_id": syllabus_id,
        "department": request.form.get("department", ""),
        "program": request.form.get("program", ""),
        "semester": request.form.get("semester", ""),
        "subject_code": request.form.get("subject_code", ""),
        "subject_name": request.form.get("subject_name", ""),
    }
    SYLLABI[syllabus_id] = metadata

    return jsonify({"success": True, "syllabus_id": syllabus_id})


# 🔹 List Syllabi (frontend calls: /list_syllabi)
@app.route("/list_syllabi", methods=["GET"])
def list_syllabi():
    return jsonify(list(SYLLABI.values()))


# (optionally keep old route names as aliases)
@app.route("/ingest", methods=["POST"])
def ingest_alias():
    return ingest_syllabus()


@app.route("/syllabi", methods=["GET"])
def list_alias():
    return list_syllabi()

def split_questions(raw: str):
    """
    Split a combined text like:
    'Q1: ... Q2: ... Q3: ...'
    or multiple lines into individual questions.
    """
    if not raw:
        return []

    text = raw.strip()

    # Try to split on patterns like Q1:, Q2:, Q3:
    parts = re.split(r'(Q\d+\s*:)', text)
    if len(parts) > 1:
        questions = []
        current_label = None
        current_text = ""

        for part in parts:
            if not part.strip():
                continue
            if re.match(r'Q\d+\s*:', part):
                # starting a new question
                if current_label and current_text.strip():
                    questions.append(current_text.strip())
                current_label = part.strip()
                current_text = ""
            else:
                current_text += part

        if current_label and current_text.strip():
            questions.append(current_text.strip())

        return questions

    # Fallback: split by non-empty lines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 1:
        return lines

    # Single question
    return [text]


@app.route("/analyze_question", methods=["POST","OPTIONS"])
def analyze():
    #respond to CORS preflight immediately
    if request.method == "OPTIONS":
        return ('', 200)    
    # Support both JSON and multipart/form-data
    if request.form:
        data = request.form
        files = request.files
    else:
        data = request.get_json(silent=True) or {}
        files = {}

    mode = data.get("mode", "text")  # "text" or "pdf"
    syllabus_id = data.get("syllabus_id")
    threshold = float(data.get("threshold", 0.2))

    # 1) Get question text (from textarea or uploaded PDF)
    if mode == "pdf":
        if "file" not in files:
            return jsonify({"error": "No question PDF uploaded"}), 400
        from processors.pdf_reader import extract_text_from_pdf
        question_text = extract_text_from_pdf(files["file"])
    else:
        question_text = data.get("question", "").strip()

    if not question_text:
        return jsonify({"error": "Empty question"}), 400

    # 🔹 NEW: split into individual questions
    questions = split_questions(question_text)

    # If only one question → keep old single behaviour
    if len(questions) == 1:
        q_text = questions[0]
        result = vector_db.query(q_text, k=3)

        distances = result.get("distances") or []
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]

        similarity = 0.0
        top_chunks = []

        if distances and distances[0]:
            first_distance = distances[0][0]
            if first_distance is None:
                similarity = 0.0
            else:
                similarity = float(1.0 - first_distance)

            similarity = max(0.0, min(1.0, similarity))

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                sim = 1.0 - d
                sim = max(0.0, min(1.0, sim))

                top_chunks.append(
                    {
                        "text": doc,
                        "distance": d,
                        "similarity": sim,
                        "module": meta.get("module") if isinstance(meta, dict) else None,
                    }
                )

        gatekeeper_passed = similarity >= threshold
        is_in_syllabus = gatekeeper_passed

        if not gatekeeper_passed:
            return jsonify(
                {
                    "mode": "single",
                    "question": q_text,
                    "similarity_score": similarity,
                    "is_in_syllabus": False,
                    "gatekeeper_passed": False,
                    "reason": "Below similarity threshold",
                    "top_chunks": top_chunks,
                    "llm_decision": None,
                    "llm_justification": None,
                }
            )

        return jsonify(
            {
                "mode": "single",
                "question": q_text,
                "similarity_score": similarity,
                "is_in_syllabus": True,
                "gatekeeper_passed": True,
                "reason": "Gatekeeper PASS (LLM Validator pending)",
                "top_chunks": top_chunks,
                "llm_decision": "YES",
                "llm_justification": "Similarity above threshold; LLM validator not yet integrated.",
            }
        )

    # 🔹 MULTI-QUESTION (batch) MODE
    batch_results = []

    for q_text in questions:
        result = vector_db.query(q_text, k=3)

        distances = result.get("distances") or []
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]

        similarity = 0.0
        top_chunks = []

        if distances and distances[0]:
            first_distance = distances[0][0]
            if first_distance is None:
                similarity = 0.0
            else:
                similarity = float(1.0 - first_distance)

            similarity = max(0.0, min(1.0, similarity))

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                sim = 1.0 - d
                sim = max(0.0, min(1.0, sim))

                top_chunks.append(
                    {
                        "text": doc,
                        "distance": d,
                        "similarity": sim,
                        "module": meta.get("module") if isinstance(meta, dict) else None,
                    }
                )

        gatekeeper_passed = similarity >= threshold
        is_in_syllabus = gatekeeper_passed

        batch_results.append(
            {
                "question": q_text,
                "similarity_score": similarity,
                "is_in_syllabus": is_in_syllabus,
                "gatekeeper_passed": gatekeeper_passed,
                "reason": "Below similarity threshold" if not gatekeeper_passed else "Gatekeeper PASS (LLM Validator pending)",
                "top_chunks": top_chunks,
                "llm_decision": "YES" if gatekeeper_passed else None,
                "llm_justification": "Similarity above threshold; LLM validator not yet integrated."
                if gatekeeper_passed
                else None,
            }
        )

    # return all questions' results
    return jsonify(
        {
            "mode": "batch",
            "questions": batch_results,
        }
    )


   


if __name__ == "__main__":
    app.run(port=5000, debug=True)
