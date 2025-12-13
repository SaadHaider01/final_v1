import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

# quick debug print (temporary) to verify it's set before any imports
#print("CHROMA_TELEMETRY_ENABLED =", os.environ.get("CHROMA_TELEMETRY_ENABLED"))

from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import re
from validators.llm_validator import validate_question


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


# @app.route("/syllabi", methods=["GET"])
# def list_alias():
#     return list_syllabi()

def split_questions(raw: str):
    if not raw:
        return []

    text = raw.strip()

    # NEW: handle both Q1: and Q1.
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

    # fallback: split by newlines
    return [p.strip() for p in text.split("\n") if p.strip()]


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
            print("RAW QUESTION TEXT RECEIVED:", question_text)

        if not question_text:
            return jsonify({"error": "Empty question"}), 400

        # 🔹 NEW: split into individual questions
        questions = split_questions(question_text)
        print("SPLIT QUESTIONS:", questions)   

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

            if gatekeeper_passed:
            # call local LLM to validate and map module
                try:
                    llm_res = validate_question(q_text, top_chunks)
                    llm_decision = llm_res.get("llm_decision")
                    llm_justification = llm_res.get("llm_justification")
                    llm_module = llm_res.get("llm_module")
                except Exception as e:
                    # fail-safe: if LLM errors, mark as pending and return gatekeeper result
                    llm_decision = None
                    llm_justification = f"LLM validator error: {str(e)}"
                    llm_module = None

                return jsonify(
                    {
                        "mode": "single",
                        "question": q_text,
                        "similarity_score": similarity,
                        "is_in_syllabus": (llm_decision == "YES") if llm_decision else True,
                        "gatekeeper_passed": True,
                        "reason": "Gatekeeper PASS + LLM validator",
                        "top_chunks": top_chunks,
                        "llm_decision": llm_decision,
                        "llm_justification": llm_justification,
                        "llm_module": llm_module,
                        "llm_raw": llm_res.get("raw_model_text") if isinstance(llm_res, dict) else None,
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

                    top_chunks.append({
                        "text": doc,
                        "distance": d,
                        "similarity": sim,
                        "module": meta.get("module") if isinstance(meta, dict) else None,
                    })

            gatekeeper_passed = similarity >= threshold
            is_in_syllabus = gatekeeper_passed

            # Call LLM validator if gatekeeper passes
            if gatekeeper_passed:
                try:
                    llm_res = validate_question(q_text, top_chunks)
                    llm_decision = llm_res.get("llm_decision")
                    llm_justification = llm_res.get("llm_justification")
                    llm_module = llm_res.get("llm_module")
                except Exception as e:
                    llm_decision = None
                    llm_justification = f"LLM error: {str(e)}"
                    llm_module = None
            else:
                llm_decision = None
                llm_justification = None
                llm_module = None

            batch_results.append({
            "question": q_text,
            "similarity_score": similarity,
            "is_in_syllabus": (llm_decision == "YES") if llm_decision else gatekeeper_passed,
            "gatekeeper_passed": gatekeeper_passed,
            "reason": "Gatekeeper PASS (LLM validated)" if llm_decision else ("Below similarity threshold" if not gatekeeper_passed else "Gatekeeper PASS (LLM pending)"),
            "top_chunks": top_chunks,
            "llm_decision": llm_decision,
            "llm_justification": llm_justification,
            "llm_module": llm_module,
            })

        print("RETURNING BATCH RESPONSE:", batch_results)
        # return all questions' results
        return jsonify(
            {
                "mode": "batch",
                "questions": batch_results,
            }
        )


    


if __name__ == "__main__":
    print("Starting Flask backend...")
    app.run(port=5000, debug=True)
