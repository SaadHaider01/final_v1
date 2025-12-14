import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import re

from models.embedder import Embedder
from processors.pdf_reader import extract_text_from_pdf
from processors.text_chunker import chunk_syllabus
from vectorstores.chroma_store import VectorStore

from services.question_analyzer import analyze_question

# --------------------------------------------------
# App setup
# --------------------------------------------------
app = Flask(__name__)
CORS(app)

embedder = Embedder()
vector_db = VectorStore(embed_fn=embedder.embed)

SYLLABI = {}
SYLLABUS_CHUNKS = {}

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def split_questions(raw: str):
    if not raw:
        return []

    text = raw.strip()

    # Handle Q1:, Q1. formats
    parts = re.split(r'(Q\d+\s*[:.])', text)

    if len(parts) > 1:
        questions = []
        current = ""

        for part in parts:
            if re.match(r'Q\d+\s*[:.]', part):
                if current.strip():
                    questions.append(current.strip())
                current = ""
            else:
                current += part

        if current.strip():
            questions.append(current.strip())

        return questions

    return [p.strip() for p in text.split("\n") if p.strip()]

# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.route("/ingest_syllabus", methods=["POST"])
def ingest_syllabus():
    mode = request.form.get("mode", "pdf")
    syllabus_id = str(uuid.uuid4())

    if mode == "pdf":
        if "file" not in request.files:
            return jsonify({"error": "No PDF uploaded"}), 400
        text = extract_text_from_pdf(request.files["file"])
    else:
        text = request.form.get("text", "")
        if not text.strip():
            return jsonify({"error": "Empty syllabus text"}), 400

    chunks = chunk_syllabus(text)
    vector_db.add_syllabus(syllabus_id, chunks)
    SYLLABUS_CHUNKS[syllabus_id] = chunks

    SYLLABI[syllabus_id] = {
        "syllabus_id": syllabus_id,
        "department": request.form.get("department", ""),
        "program": request.form.get("program", ""),
        "semester": request.form.get("semester", ""),
        "subject_code": request.form.get("subject_code", ""),
        "subject_name": request.form.get("subject_name", ""),
    }

    return jsonify({"success": True, "syllabus_id": syllabus_id})


@app.route("/list_syllabi", methods=["GET"])
def list_syllabi():
    return jsonify(list(SYLLABI.values()))


@app.route("/analyze_question", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return ("", 200)

    data = request.form if request.form else request.get_json(silent=True) or {}
    files = request.files if request.form else {}

    mode = data.get("mode", "text")
    threshold = float(data.get("threshold", 0.2))

    if mode == "pdf":
        if "file" not in files:
            return jsonify({"error": "No question PDF uploaded"}), 400
        question_text = extract_text_from_pdf(files["file"])
    else:
        question_text = data.get("question", "").strip()

    if not question_text:
        return jsonify({"error": "Empty question"}), 400

    questions = split_questions(question_text)

    # --------------------------------------------------
    # SINGLE QUESTION
    # --------------------------------------------------
    if len(questions) == 1:
        q_text = questions[0]

        result = vector_db.query(q_text, k=3)
        distances = result.get("distances") or [[]]
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]

        top_chunks = []
        similarity = 0.0

        if distances and distances[0]:
            similarity = max(0.0, min(1.0, 1.0 - float(distances[0][0])))

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                top_chunks.append({
                    "text": doc,
                    "distance": d,
                    "similarity": max(0.0, min(1.0, 1.0 - d)),
                    "module": meta.get("module") if isinstance(meta, dict) else None,
                })

        analysis = analyze_question(
            question=q_text,
            similarity=similarity,
            threshold=threshold,
            top_chunks=top_chunks,
        )

        return jsonify({
            "mode": "single",
            "question": q_text,
            "similarity_score": similarity,
            "is_in_syllabus": analysis["is_in_syllabus"],
            "gatekeeper_passed": analysis["gatekeeper_passed"],
            "reason": analysis["reason"],
            "top_chunks": top_chunks,
            "llm_decision": analysis["llm"]["llm_decision"] if analysis["llm"] else None,
            "llm_justification": analysis["llm"]["llm_justification"] if analysis["llm"] else None,
        })

    # --------------------------------------------------
    # BATCH MODE
    # --------------------------------------------------
    batch_results = []

    for q_text in questions:
        result = vector_db.query(q_text, k=3)
        distances = result.get("distances") or [[]]
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]

        similarity = 0.0
        top_chunks = []

        if distances and distances[0]:
            similarity = max(0.0, min(1.0, 1.0 - float(distances[0][0])))

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                top_chunks.append({
                    "text": doc,
                    "distance": d,
                    "similarity": max(0.0, min(1.0, 1.0 - d)),
                    "module": meta.get("module") if isinstance(meta, dict) else None,
                })

        analysis = analyze_question(
            question=q_text,
            similarity=similarity,
            threshold=threshold,
            top_chunks=top_chunks,
        )

        batch_results.append({
            "question": q_text,
            "similarity_score": similarity,
            "is_in_syllabus": analysis["is_in_syllabus"],
            "gatekeeper_passed": analysis["gatekeeper_passed"],
            "reason": analysis["reason"],
            "top_chunks": top_chunks,
            "llm_decision": analysis["llm"]["llm_decision"] if analysis["llm"] else None,
            "llm_justification": analysis["llm"]["llm_justification"] if analysis["llm"] else None,
        })

    return jsonify({
        "mode": "batch",
        "questions": batch_results,
    })


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    print("Starting Flask backend...")
    app.run(port=5000, debug=True)
