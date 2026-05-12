import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import re
import json
import tempfile
import requests as http_requests

from models.embedder import Embedder
from processors.pdf_reader import extract_text_from_pdf
from processors.metadata_extractor import extract_metadata # Added
from processors.text_chunker import chunk_syllabus, chunk_syllabus_with_modules
from vectorstores.chroma_store import VectorStore

from services.question_analyzer import analyze_question
from services.co_mapper import CoMapper            # Feature 3

# --------------------------------------------------
# App setup
# --------------------------------------------------
app = Flask(__name__)
CORS(app)

embedder   = Embedder()
vector_db  = VectorStore(embed_fn=embedder.embed)
co_mapper  = CoMapper(embed_fn=embedder.embed)     # Feature 3 — shares same embedder

SYLLABI         = {}
SYLLABUS_CHUNKS = {}

# --------------------------------------------------
# Helpers
# --------------------------------------------------
# --------------------------------------------------
# Helpers
# --------------------------------------------------
def split_questions(raw: str):
    if not raw:
        return []

    text = raw.strip()

    # Handle Q1:, Q1. formats
    parts = re.split(r'(Q\d+\s*[:.] )', text)

    if len(parts) > 1:
        questions = []
        current   = ""

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


# Module-name extractor — reads from chunk text since VectorStore metadata
# does not store a module field. Handles two formats:
#
#  Format A — explicit prefix:  "M1:", "Module 1:", "UNIT 1:"
#  Format B — table row:        "1  Introduction: topics..."
#                               (bare number, then title ending in colon)
_MODULE_RE = re.compile(
    r"(?:^|\n)\s*"
    r"(?:M(?:odule)?\s*([\dIVX]+)\s*[:–-]|UNIT\s*([\dIVX]+)\s*[:–-])"
    r"\s*(.+)",
    re.IGNORECASE,
)

# Matches: start-of-line, optional whitespace, 1-2 digit unit number,
# whitespace, then a capitalised title word ending in a colon.
_BARE_UNIT_RE = re.compile(
    r"(?:^|\n)\s*(\d{1,2})\s+([A-Z][^:\n]{2,60}?):\s*",
)

def _extract_module(text: str):
    """Return a module label from chunk text, or None."""
    if not text:
        return None

    # Try Format A first (explicit prefix)
    m = _MODULE_RE.search(text)
    if m:
        num   = (m.group(1) or m.group(2) or "").strip()
        title = m.group(3).strip()[:60]
        return f"Unit {num}: {title}" if num else title

    # Try Format B (bare number + capitalised title, as in university tables)
    m2 = _BARE_UNIT_RE.search(text)
    if m2:
        num   = m2.group(1).strip()
        title = m2.group(2).strip()[:50]
        return f"Unit {num}: {title}"

    return None


# ── Reference-book detection ──────────────────────────────────────────────────
# Catches bibliographic entries that get chunked as numbered topics.
# Two-pronged approach:
#   1. Regex for short "Title, Author, ABBREV" entries
#   2. Keyword scan for publisher names in short chunks

_REFERENCE_BOOK_RE = re.compile(
    r"^\s*(?:\d{1,2}\.\s*)?"           # optional leading number: "1. " or "8. "
    r".{5,60},"                         # title (5-60 chars) followed by comma
    r"\s*[A-Z][A-Za-z.\s]{1,30},"      # author name(s) followed by comma
    r"\s*[A-Z]{2,5}\s*\.?\s*$",        # publisher abbreviation at end
    re.MULTILINE,
)

# Common publisher / bibliographic keywords (case-insensitive scan)
_PUBLISHER_KW = re.compile(
    r"Publishing|Publishers|Press|Edition|McGraw|Pearson|Wiley|Springer|Elsevier|"
    r"Oxford|Cambridge|Prentice|Tata|Jaico|Housing|Ltd\.?|Inc\.?|"
    r"\bPHI\b|\bEPH\b|\bTMH\b|\bSPD\b|\bBPB\b",
    re.IGNORECASE,
)

# Strong bibliographic signals — patterns that almost certainly indicate
# a reference book entry, even if the title contains syllabus-sounding words.
_BIBLIO_SIGNAL = re.compile(
    r"""\bby\s+[A-Z][a-z]"""             # "by Stavronlakis", "by Reynolds"
    r"""|\u201c[^\u201d]{5,}\u201d"""     # "curly-quoted title"
    r'''|"[^"]{5,}"'''                    # "straight-quoted title"
    r"""|'[^']{5,}'"""                    # 'single-quoted title'
    r"""|\b\d{1,2}(?:st|nd|rd|th)\s+Ed""" # "2nd Edition"
    r"""|\bISBN\b""",                     # ISBN number
    re.IGNORECASE,
)

# Words that strongly indicate real syllabus content, not a reference
_SYLLABUS_SIGNAL = re.compile(
    r"Overview|Definition|Introduction|Concept|Architecture|Protocol|"
    r"Mechanism|Technique|Algorithm|Application|Type[s]?|Model[s]?|"
    r"Security|Management|System|Design|Analysis|Method",
    re.IGNORECASE,
)


def _is_reference_entry(text: str) -> bool:
    """
    Return True if the chunk looks like a bibliographic reference
    rather than actual syllabus content.

    Catches patterns like:
      - "E-Commerce, M.M. Oka, EPH"
      - "Loshin Pete, Murphy P.A. : Electronic Commerce, Jaico Publishing Housing."
      - '8. "Third Generation Mobile Telecommunication systems", by P.Stavronlakis, Springer Publishers.'
    """
    text = text.strip()
    # Real topics are longer — references are short citation lines
    if len(text) > 150:
        return False

    # Approach 1: regex for  Title, Author, ABBREV  pattern
    if _REFERENCE_BOOK_RE.match(text):
        return True

    # Approach 2: publisher keyword + bibliographic signal = always a reference
    #   (overrides syllabus-signal safety valve — book titles often contain
    #    words like "Systems", "Security", "Management")
    has_publisher = _PUBLISHER_KW.search(text)
    has_biblio    = _BIBLIO_SIGNAL.search(text)

    if has_publisher and has_biblio:
        return True

    # Approach 3: publisher keyword + comma, but no syllabus signal
    if len(text) < 150 and text.count(",") >= 1 and has_publisher:
        if not _SYLLABUS_SIGNAL.search(text):
            return True

    return False


def _dedup_chunks(chunks: list) -> list:
    """Remove duplicate, overlapping, and reference-book chunks. Keep lowest-distance copy."""
    result: list = []
    
    # Sort by distance (best first)
    sorted_chunks = sorted(chunks, key=lambda x: x.get("distance", 1.0))

    for c in sorted_chunks:
        txt = c.get("text", "").strip()
        if not txt:
            continue

        # Skip reference book entries
        if _is_reference_entry(txt):
            continue
            
        # Check if this text (or a significant part of it) is already in results
        is_dup = False
        for existing in result:
            ext_txt = existing.get("text", "").strip()
            # If one is a substring of the other and they are from the same module
            if (txt.lower() in ext_txt.lower() or ext_txt.lower() in txt.lower()) and \
               c.get("module") == existing.get("module"):
                is_dup = True
                break
        
        if not is_dup:
            result.append(c)
            
    return result


def _smart_filter_chunks(chunks: list, same_gap: float = 0.02, cross_gap: float = 0.04) -> list:
    """
    Reduce noise by keeping only the most relevant matches.

    Algorithm:
      1. Always keep match #1 (best similarity).
      2. For subsequent matches, keep ONLY if:
         a. SAME module as #1 AND within `same_gap` (2%) of the best, OR
         b. DIFFERENT module AND within `cross_gap` (4%) of the best
            (handles cross-module questions without letting unrelated
            subjects sneak in).
      3. Cap at 3 results total.

    Single-module question  → typically returns 1 result
    Cross-module question   → returns 1 per relevant module (up to 3)
    """
    if not chunks:
        return []

    # Already sorted by distance (best first) from _dedup_chunks
    best_sim = chunks[0].get("similarity", 0.0)
    kept = [chunks[0]]
    kept_modules = {chunks[0].get("module") or "Unknown"}

    for c in chunks[1:]:
        if len(kept) >= 3:
            break

        c_sim    = c.get("similarity", 0.0)
        c_module = c.get("module") or "Unknown"
        gap      = best_sim - c_sim

        if c_module in kept_modules:
            # Same module — only keep if extremely close to #1
            if gap <= same_gap:
                kept.append(c)
        else:
            # Different module — keep with a slightly more lenient gap
            if gap <= cross_gap:
                kept.append(c)
                kept_modules.add(c_module)

    return kept


# --------------------------------------------------
# Helper: build enriched response dict
# --------------------------------------------------
def _build_result(q_text, similarity, top_chunks, analysis):
    """Assemble the full per-question result dict."""
    return {
        "question":          q_text,
        "similarity_score":  similarity,
        "is_in_syllabus":    analysis["is_in_syllabus"],
        "gatekeeper_passed": analysis["gatekeeper_passed"],
        "reason":            analysis["reason"],
        # ---- new fields ----
        "modules_detected":  analysis["modules_detected"],
        "bloom_level":       analysis["bloom_level"],
        "difficulty":        analysis["difficulty"],
        "mapped_co":         analysis["mapped_co"],
        "mapped_pco":        analysis["mapped_pco"],
        # ---- existing LLM fields ----
        "llm_decision":      analysis["llm"]["llm_decision"]     if analysis["llm"] else None,
        "llm_justification": analysis["llm"]["llm_justification"] if analysis["llm"] else None,
        "llm_module":        analysis["llm"]["llm_module"]        if analysis["llm"] else None,
        "top_chunks":        top_chunks,
    }


# --------------------------------------------------
# Helper: fetch and extract text from a URL
# --------------------------------------------------
def _fetch_text_from_url(url: str) -> str:
    """
    Download content from URL.
    - If it's a PDF (Content-Type or .pdf extension) → extract via pypdf
    - Otherwise treat as HTML/text → strip tags with basic regex
    Raises ValueError on failure.
    """
    try:
        resp = http_requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch URL: {e}")

    content_type = resp.headers.get("Content-Type", "")
    is_pdf = "pdf" in content_type.lower() or url.lower().endswith(".pdf")

    if is_pdf:
        # Write to temp file then use existing pypdf extractor
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                text = extract_text_from_pdf(f)
        finally:
            os.unlink(tmp_path)
    else:
        # Strip HTML tags
        raw = resp.text
        text = re.sub(r"<[^>]+>", " ", raw)          # remove tags
        text = re.sub(r"&\w+;", " ", text)            # remove HTML entities
        text = re.sub(r"\s{3,}", "\n\n", text)        # collapse whitespace

    if not text.strip():
        raise ValueError("Extracted text is empty. The page may require JavaScript.")

    return text.strip()


# --------------------------------------------------
# Routes — existing (unchanged contract)
# --------------------------------------------------
@app.route("/ingest_syllabus", methods=["POST"])
def ingest_syllabus():
    mode        = request.form.get("mode", "pdf")
    syllabus_id = str(uuid.uuid4())

    if mode == "pdf":
        if "file" not in request.files:
            return jsonify({"error": "No PDF uploaded"}), 400
        text = extract_text_from_pdf(request.files["file"])
    else:
        text = request.form.get("text", "")
        if not text.strip():
            return jsonify({"error": "Empty syllabus text"}), 400

    chunks = chunk_syllabus_with_modules(text)
    vector_db.add_syllabus(syllabus_id, chunks)
    SYLLABUS_CHUNKS[syllabus_id] = [c for c, _ in chunks]

    # Automatic Metadata Extraction (Feature: Academic Context)
    extracted = extract_metadata(text)

    SYLLABI[syllabus_id] = {
        "syllabus_id":  syllabus_id,
        "bos":          request.form.get("bos") or extracted.get("bos") or "",
        "department":   request.form.get("department") or extracted.get("department") or "",
        "program":      request.form.get("program") or extracted.get("program") or "",
        "semester":     request.form.get("semester") or extracted.get("semester") or "",
        "subject_code": request.form.get("subject_code") or extracted.get("subject_code") or "",
        "subject_name": request.form.get("subject_name") or extracted.get("subject_name") or "",
        "extracted":    extracted # store for debugging
    }

    cos_stored = pcos_stored = 0

    # Feature 3 — optional CO ingestion
    cos_raw = request.form.get("cos", "")
    if cos_raw:
        try:
            cos = json.loads(cos_raw)
            if isinstance(cos, list) and cos:
                cos_stored = co_mapper.add_cos(syllabus_id, cos)
        except (json.JSONDecodeError, KeyError):
            pass

    # Feature 3B — optional PCO ingestion
    pcos_raw = request.form.get("pcos", "")
    if pcos_raw:
        try:
            pcos = json.loads(pcos_raw)
            if isinstance(pcos, list) and pcos:
                pcos_stored = co_mapper.add_pcos(syllabus_id, pcos)
        except (json.JSONDecodeError, KeyError):
            pass

    return jsonify({
        "success":     True,
        "syllabus_id": syllabus_id,
        "cos_stored":  cos_stored,
        "pcos_stored": pcos_stored,
    })


# --------------------------------------------------
# NEW: Ingest syllabus from URL (Upgrade B)
# --------------------------------------------------
@app.route("/ingest_from_url", methods=["POST"])
def ingest_from_url():
    """
    Download a syllabus from a public URL (PDF or HTML) and ingest it.

    JSON body:
        url          (required)
        bos          (optional)
        department   (optional)
        program      (optional)
        semester     (optional)
        subject_code (optional)
        subject_name (optional)
        cos          (optional JSON string)
        pcos         (optional JSON string)
    """
    data = request.get_json(silent=True) or {}
    url  = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        text = _fetch_text_from_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    syllabus_id = str(uuid.uuid4())
    chunks      = chunk_syllabus_with_modules(text)
    vector_db.add_syllabus(syllabus_id, chunks)
    SYLLABUS_CHUNKS[syllabus_id] = [c for c, _ in chunks]

    # Automatic Metadata Extraction
    extracted = extract_metadata(text)

    SYLLABI[syllabus_id] = {
        "syllabus_id":  syllabus_id,
        "bos":          data.get("bos") or extracted.get("bos") or "",
        "department":   data.get("department") or extracted.get("department") or "",
        "program":      data.get("program") or extracted.get("program") or "",
        "semester":     data.get("semester") or extracted.get("semester") or "",
        "subject_code": data.get("subject_code") or extracted.get("subject_code") or "",
        "subject_name": data.get("subject_name") or extracted.get("subject_name") or data.get("url", "")[:60],
    }

    cos_stored = pcos_stored = 0

    cos_raw = data.get("cos", "")
    if cos_raw:
        try:
            cos = json.loads(cos_raw) if isinstance(cos_raw, str) else cos_raw
            if isinstance(cos, list) and cos:
                cos_stored = co_mapper.add_cos(syllabus_id, cos)
        except (json.JSONDecodeError, KeyError):
            pass

    pcos_raw = data.get("pcos", "")
    if pcos_raw:
        try:
            pcos = json.loads(pcos_raw) if isinstance(pcos_raw, str) else pcos_raw
            if isinstance(pcos, list) and pcos:
                pcos_stored = co_mapper.add_pcos(syllabus_id, pcos)
        except (json.JSONDecodeError, KeyError):
            pass

    return jsonify({
        "success":     True,
        "syllabus_id": syllabus_id,
        "cos_stored":  cos_stored,
        "pcos_stored": pcos_stored,
        "source":      url,
    })


@app.route("/list_syllabi", methods=["GET"])
def list_syllabi():
    return jsonify(list(SYLLABI.values()))


@app.route("/delete_syllabus", methods=["POST"])
def delete_syllabus():
    data        = request.get_json(silent=True) or {}
    syllabus_id = data.get("syllabus_id", "")
    if syllabus_id in SYLLABI:
        del SYLLABI[syllabus_id]
    # Also remove from vector store and chunk cache
    vector_db.delete_syllabus(syllabus_id)
    SYLLABUS_CHUNKS.pop(syllabus_id, None)
    return jsonify({"success": True})


@app.route("/purge_all", methods=["POST"])
def purge_all():
    """
    Nuclear option: wipe ALL syllabi from memory AND ChromaDB.
    Use this to clear stale data after code changes.
    """
    count = len(SYLLABI)
    for sid in list(SYLLABI.keys()):
        vector_db.delete_syllabus(sid)
    SYLLABI.clear()
    SYLLABUS_CHUNKS.clear()

    # Also try to nuke any orphaned vectors not tracked in SYLLABI
    try:
        total_in_db = vector_db.collection.count()
        if total_in_db > 0:
            # Get all IDs and delete them
            all_data = vector_db.collection.get()
            if all_data and all_data.get("ids"):
                vector_db.collection.delete(ids=all_data["ids"])
    except Exception as e:
        print(f"Purge orphan cleanup error: {e}")

    return jsonify({
        "success":          True,
        "syllabi_removed":  count,
        "message":          "All data purged. Re-ingest your syllabi.",
    })



@app.route("/analyze_question", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return ("", 200)

    data  = request.form if request.form else request.get_json(silent=True) or {}
    files = request.files if request.form else {}

    mode        = data.get("mode", "text")
    threshold   = float(data.get("threshold", 0.2))
    syllabus_id = data.get("syllabus_id", None)

    if mode == "pdf":
        if "file" not in files:
            return jsonify({"error": "No question PDF uploaded"}), 400
        question_text = extract_text_from_pdf(files["file"])
    else:
        question_text = data.get("question", "").strip()

    if not question_text:
        return jsonify({"error": "Empty question"}), 400

    questions = split_questions(question_text)

    # Process each question (handles both single and batch)
    processed_results = []
    for q_text in questions:
        # Pass syllabus_id to filter the vector search! (Fixes mismatch)
        result    = vector_db.query(q_text, k=8, syllabus_id=syllabus_id) # increased k to 8 before dedup
        distances = result.get("distances") or [[]]
        docs      = result.get("documents") or [[]]
        metas     = result.get("metadatas") or [[]]

        similarity = 0.0
        top_chunks = []

        if distances and distances[0]:
            # Overall similarity is based on the closest match
            similarity = max(0.0, min(1.0, 1.0 - float(distances[0][0])))

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                top_chunks.append({
                    "text":       doc,
                    "distance":   d,
                    "similarity": max(0.0, min(1.0, 1.0 - d)),
                    "module": (
                        meta.get("module") or _extract_module(doc)
                    ) if isinstance(meta, dict) else _extract_module(doc),
                })

        # Dedup → reference filter → smart relevance filter
        top_chunks = _smart_filter_chunks(_dedup_chunks(top_chunks))

        analysis = analyze_question(
            question=q_text,
            similarity=similarity,
            threshold=threshold,
            top_chunks=top_chunks,
            co_mapper=co_mapper,
            syllabus_id=syllabus_id,
        )
        
        processed_results.append(_build_result(q_text, similarity, top_chunks, analysis))

    if len(questions) == 1:
        return jsonify({"mode": "single", **processed_results[0]})
    
    return jsonify({"mode": "batch", "questions": processed_results})


# --------------------------------------------------
# Routes — BOS endpoints (Feature 4)
# --------------------------------------------------

@app.route("/bos", methods=["GET"])
def get_bos():
    bos_values = sorted({s["bos"] for s in SYLLABI.values() if s.get("bos")})
    return jsonify(bos_values)


@app.route("/departments", methods=["GET"])
def get_departments():
    bos_filter = request.args.get("bos", "").strip()
    depts = sorted({
        s["department"]
        for s in SYLLABI.values()
        if s.get("department") and (not bos_filter or s.get("bos") == bos_filter)
    })
    return jsonify(depts)


@app.route("/subjects", methods=["GET"])
def get_subjects():
    sem_filter = request.args.get("semester", "").strip()
    subjects = sorted({
        s["subject_name"]
        for s in SYLLABI.values()
        if s.get("subject_name") and (not sem_filter or s.get("semester") == sem_filter)
    })
    return jsonify(subjects)


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    print("Starting Flask backend...")
    app.run(port=5000, debug=True)
