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
from processors.document_reader import extract_text_from_file
from processors.metadata_extractor import extract_metadata # Added
from processors.text_chunker import chunk_syllabus, chunk_syllabus_with_modules
from processors.curriculum_segmenter import segment_curriculum
from vectorstores.chroma_store import VectorStore
from services.chunk_cleaner import clean_retrieved_chunks
from services.chunk_quality import filter_chunks_for_embedding   # NEW: pre-embedding quality gate

from services.question_analyzer import analyze_question
from services.co_mapper import CoMapper            # Feature 3
from services.concept_expander import ConceptStore

# --------------------------------------------------
# App setup
# --------------------------------------------------
app = Flask(__name__)
CORS(app)

embedder   = Embedder()
vector_db  = VectorStore(embed_fn=embedder.embed)
co_mapper  = CoMapper(embed_fn=embedder.embed)     # Feature 3 — shares same embedder
concept_store = ConceptStore(embed_fn=embedder.embed)

SYLLABI         = {}
SYLLABUS_CHUNKS = {}
PARSED_SEGMENTS = {}  # Temporary store: parse_id → list of segment dicts (not yet embedded)


# --------------------------------------------------
# Startup: Hydrate SYLLABI from persisted ChromaDB
# --------------------------------------------------
def _hydrate_syllabi_from_chroma():
    """
    On every server start, rebuild the in-memory SYLLABI dict from ChromaDB
    metadata so that the frontend's /list_syllabi returns the correct data
    even after a server restart.

    ChromaDB persists vectors to disk; SYLLABI is in-memory only.
    Without hydration, a restart causes SYLLABI = {} while vectors still exist,
    making the frontend show an empty list yet the 'already_ingested' check
    in /parse_curriculum returns True (causing 'already selected but nothing shown').
    """
    try:
        all_data = vector_db.collection.get(include=["metadatas"])
        metas    = all_data.get("metadatas") or []

        seen_ids = set()
        hydrated = 0

        for meta in metas:
            sid = meta.get("syllabus_id")
            if not sid:
                continue
            
            # Extract module if it exists
            mod = meta.get("module")
            
            # If new syllabus, initialize it
            if sid not in seen_ids:
                seen_ids.add(sid)
                SYLLABI[sid] = {
                    "syllabus_id":           sid,
                    "curriculum_department":  meta.get("curriculum_department") or meta.get("department", ""),
                    "department":             meta.get("department", ""),
                    "subject_owner_department": meta.get("subject_owner_department", ""),
                    "semester":              meta.get("semester", ""),
                    "subject_code":          meta.get("subject_code", ""),
                    "subject_name":          meta.get("subject_name", "Unknown Subject"),
                    "elective_type":         meta.get("elective_type", "CORE"),
                    "metadata_confidence":   meta.get("metadata_confidence", 0.7),
                    "bos":                   meta.get("bos", ""),
                    "program":               meta.get("program", ""),
                    "modules":               [],
                }
                hydrated += 1
            
            # Append unique modules
            if mod and mod.lower() != "unknown" and mod not in SYLLABI[sid]["modules"]:
                SYLLABI[sid]["modules"].append(mod)

        if hydrated:
            print(f"[Startup] Hydrated {hydrated} syllabus entries from ChromaDB.")
        else:
            print("[Startup] ChromaDB is empty — no prior ingestions found.")

    except Exception as e:
        print(f"[Startup] Hydration failed (non-fatal): {e}")


_hydrate_syllabi_from_chroma()

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

def _calculate_keyword_overlap(question: str, chunk_text: str) -> float:
    """Calculate simple lexical overlap of technical terms between question and chunk."""
    q_words = set(w for w in re.findall(r'\b[a-zA-Z0-9]{4,}\b', question.lower()))
    if not q_words:
        return 0.0
    c_words = set(w for w in re.findall(r'\b[a-zA-Z0-9]{4,}\b', chunk_text.lower()))
    overlap = q_words.intersection(c_words)
    return len(overlap) / len(q_words)


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
        # ---- retrieval fields ----
        "retrieval_status":  analysis.get("retrieval_status", "MATCH_FOUND"),
        "match_strength":    analysis.get("match_strength", "WEAK_MATCH"),
        "match_type":        analysis.get("match_type", "OUT_OF_CURRICULUM"),
        "modules_detected":  analysis["modules_detected"],
        "bloom_level":       analysis["bloom_level"],
        "difficulty":        analysis["difficulty"],
        "mapped_co":         analysis["mapped_co"],
        "mapped_pco":        analysis["mapped_pco"],
        # ---- existing LLM fields ----
        "llm_decision":      analysis["llm"]["llm_decision"]     if analysis["llm"] else None,
        "llm_justification": analysis["llm"]["llm_justification"] if analysis["llm"] else None,
        "llm_module":        analysis["llm"]["llm_module"]        if analysis["llm"] else None,
        "top_chunks":        analysis.get("top_chunks", top_chunks),
        # ---- diagnostics ----
        "semantic_score":    top_chunks[0].get("semantic_score", similarity) if top_chunks else 0.0,
        "keyword_overlap_score": top_chunks[0].get("keyword_overlap_score", 0.0) if top_chunks else 0.0,
        "concept_boost":     top_chunks[0].get("concept_boost", 0.0) if top_chunks else 0.0,
        "final_score":       similarity,
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

    content_type = resp.headers.get("Content-Type", "").lower()
    url_lower = url.lower()
    
    is_doc = any(ext in content_type for ext in ["pdf", "word", "presentation"]) or \
             any(url_lower.endswith(ext) for ext in [".pdf", ".docx", ".pptx"])

    if is_doc:
        # Determine suffix for temp file
        suffix = ".pdf"
        if "word" in content_type or url_lower.endswith(".docx"):
            suffix = ".docx"
        elif "presentation" in content_type or url_lower.endswith(".pptx"):
            suffix = ".pptx"
            
        # Write to temp file then use document extractor
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                text = extract_text_from_file(f, tmp_path)
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

    if mode in ["pdf", "file", "document"]:
        if "file" not in request.files:
            return jsonify({"error": "No document uploaded"}), 400
        file_obj = request.files["file"]
        text = extract_text_from_file(file_obj, file_obj.filename)
    else:
        text = request.form.get("text", "")
        if not text.strip():
            return jsonify({"error": "Empty syllabus text"}), 400

    segments = segment_curriculum(text)
    
    # Fallback if no segments detected
    if not segments:
        extracted = extract_metadata(text)
        segments = [{
            "department": request.form.get("department") or extracted.get("department") or "",
            "semester": request.form.get("semester") or extracted.get("semester") or "",
            "subject_code": request.form.get("subject_code") or extracted.get("subject_code") or "",
            "subject_name": request.form.get("subject_name") or extracted.get("subject_name") or "Unknown Subject",
            "text": text
        }]

    # We might have multiple subjects in one PDF, so we generate a parent syllabus_id
    # but store each segment separately, or treat each segment as its own syllabus
    # Let's treat each segment as its own "syllabus" for the frontend to select from.
    bos_val = request.form.get("bos") or extract_metadata(text).get("bos") or ""
    program_val = request.form.get("program") or extract_metadata(text).get("program") or ""
    
    cos_stored = pcos_stored = 0
    cos_raw = request.form.get("cos", "")
    pcos_raw = request.form.get("pcos", "")
    
    segment_ids = []
    
    for seg in segments:
        seg_id = str(uuid.uuid4())
        segment_ids.append(seg_id)
        
        # Clean text and chunk, then filter out references before embedding
        raw_seg_chunks = chunk_syllabus_with_modules(seg["text"])
        ref_filtered   = [c for c in raw_seg_chunks if not _is_reference_entry(c[0])]
        # STEP 1-4: Pre-embedding quality gate — reject metadata/header chunks
        seg_chunks, purged = filter_chunks_for_embedding(ref_filtered)
        print(f"[Ingest Legacy] {seg.get('subject_name','?')}: {len(seg_chunks)} quality chunks "
              f"({purged} low-info purged)")

        if not seg_chunks:
            print(f"[Ingest Legacy] No quality chunks for {seg.get('subject_name')} — skipping segment.")
            continue

        SYLLABI[seg_id] = {
            "syllabus_id":  seg_id,
            "bos":          bos_val,
            "department":   seg["department"],
            "program":      program_val,
            "semester":     seg["semester"],
            "subject_code": seg["subject_code"],
            "subject_name": seg["subject_name"],
            "extracted":    seg # store for debugging
        }

        # Store with extra metadata
        extra_meta = {
            "bos": bos_val,
            "department": seg["department"],
            "program": program_val,
            "semester": seg["semester"],
            "subject_code": seg["subject_code"],
            "subject_name": seg["subject_name"],
        }
        vector_db.add_syllabus(seg_id, seg_chunks, extra_meta=extra_meta)
        SYLLABUS_CHUNKS[seg_id] = [c for c, _ in seg_chunks]

        # Feature 3 — optional CO/PCO ingestion (applied to all segments for now)
        if cos_raw:
            try:
                cos = json.loads(cos_raw)
                if isinstance(cos, list) and cos:
                    cos_stored += co_mapper.add_cos(seg_id, cos)
            except (json.JSONDecodeError, KeyError):
                pass

        if pcos_raw:
            try:
                pcos = json.loads(pcos_raw)
                if isinstance(pcos, list) and pcos:
                    pcos_stored += co_mapper.add_pcos(seg_id, pcos)
            except (json.JSONDecodeError, KeyError):
                pass

    return jsonify({
        "success":     True,
        "syllabus_ids": segment_ids,
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
    segments = segment_curriculum(text)
    
    if not segments:
        extracted = extract_metadata(text)
        segments = [{
            "department": data.get("department") or extracted.get("department") or "",
            "semester": data.get("semester") or extracted.get("semester") or "",
            "subject_code": data.get("subject_code") or extracted.get("subject_code") or "",
            "subject_name": data.get("subject_name") or extracted.get("subject_name") or data.get("url", "")[:60],
            "text": text
        }]

    bos_val = data.get("bos") or extract_metadata(text).get("bos") or ""
    program_val = data.get("program") or extract_metadata(text).get("program") or ""
    
    cos_stored = pcos_stored = 0
    cos_raw = data.get("cos", "")
    pcos_raw = data.get("pcos", "")

    segment_ids = []

    for seg in segments:
        seg_id = seg.get("syllabus_id") or str(uuid.uuid4())
        
        # Check if already embedded
        existing = vector_db.collection.get(where={"syllabus_id": seg_id})
        if existing and existing.get("ids"):
            print(f"[Ingestion] URL: Skipping duplicate {seg_id}")
            segment_ids.append(seg_id)
            continue
            
        segment_ids.append(seg_id)
        
        raw_seg_chunks = chunk_syllabus_with_modules(seg.get("syllabus_text", seg.get("text", "")))
        ref_filtered = [c for c in raw_seg_chunks if not _is_reference_entry(c[0])]
        clean_chunks, purged = filter_chunks_for_embedding(ref_filtered)
        
        if not clean_chunks:
            continue

        extra_meta = {
            "curriculum_department":  seg.get("curriculum_department", data.get("department", "")),
            "subject_owner_department": seg.get("subject_owner_department", ""),
            "department":             seg.get("department", data.get("department", "")),
            "semester":               seg.get("semester", data.get("semester", "")),
            "program":                seg.get("program", data.get("program", "")),
            "subject_code":           seg.get("subject_code", data.get("subject_code", "")),
            "subject_name":           seg.get("subject_name", data.get("subject_name", "")),
            "elective_type":          seg.get("elective_type", ""),
            "metadata_confidence":    seg.get("metadata_confidence", "Low"),
        }
        
        vector_db.add_syllabus(seg_id, clean_chunks, extra_meta=extra_meta)
        
        try:
            concept_store.add_syllabus_concepts(seg_id, [c for c, _ in clean_chunks])
        except Exception as e:
            pass

        SYLLABI[seg_id] = {
            "syllabus_id":  seg_id,
            "bos":          bos_val,
            "curriculum_department": extra_meta["curriculum_department"],
            "subject_owner_department": extra_meta["subject_owner_department"],
            "department":   extra_meta["department"],
            "program":      extra_meta["program"],
            "semester":     extra_meta["semester"],
            "subject_code": extra_meta["subject_code"],
            "subject_name": extra_meta["subject_name"],
            "elective_type": extra_meta["elective_type"],
            "metadata_confidence": extra_meta["metadata_confidence"],
            "modules":      seg.get("modules", []),
        }
        SYLLABUS_CHUNKS[seg_id] = [c for c, _ in clean_chunks]

        if cos_raw:
            try:
                cos = json.loads(cos_raw) if isinstance(cos_raw, str) else cos_raw
                if isinstance(cos, list) and cos:
                    cos_stored += co_mapper.add_cos(seg_id, cos)
            except (json.JSONDecodeError, KeyError):
                pass

        if pcos_raw:
            try:
                pcos = json.loads(pcos_raw) if isinstance(pcos_raw, str) else pcos_raw
                if isinstance(pcos, list) and pcos:
                    pcos_stored += co_mapper.add_pcos(seg_id, pcos)
            except (json.JSONDecodeError, KeyError):
                pass

    return jsonify({
        "success":     True,
        "syllabus_ids": segment_ids,
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



@app.route("/detect_subject", methods=["POST", "OPTIONS"])
def detect_subject():
    if request.method == "OPTIONS":
        return ("", 200)

    data  = request.form if request.form else request.get_json(silent=True) or {}
    files = request.files if request.form else {}

    mode = data.get("mode", "text")

    if mode in ["pdf", "file", "document"]:
        if "file" not in files:
            return jsonify({"error": "No document uploaded"}), 400
        file_obj = files["file"]
        text = extract_text_from_file(file_obj, file_obj.filename)
    else:
        text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "Empty text"}), 400

    extracted = extract_metadata(text)
    
    # ── Semantic Subject Detection (Step 7) ──────────────────────────────────
    # If regex didn't find a code, or to confirm, try semantic matching
    # against ingested content.
    try:
        # Use first 1000 chars for semantic detection speed
        search_text = text[:1000]
        results = vector_db.query(search_text, k=1)
        
        metas = results.get("metadatas")
        dists = results.get("distances")
        
        if metas and metas[0] and dists and dists[0]:
            top_meta = metas[0][0]
            # ChromaDB distance: 0.0 is perfect match. For cosine, distance is 1-sim.
            # Convert to similarity: sim = 1 - (dist / 2) if using cosine in Chroma
            # Or just check distance. Typical "good" distance is < 0.6 for e5 models.
            dist = dists[0][0]
            
            # If distance is low enough, we consider it a semantic match
            if dist < 0.6:
                # Prioritise semantic match for syllabus context selection
                extracted["syllabus_id"]   = top_meta.get("syllabus_id")
                extracted["subject_code"] = top_meta.get("subject_code")
                extracted["subject_name"] = top_meta.get("subject_name")
                extracted["department"]   = top_meta.get("department")
                extracted["semester"]     = top_meta.get("semester")
                
                print(f"[Detect] Semantic match found: {extracted['syllabus_id']} (dist={dist:.3f})")
    except Exception as e:
        print(f"[Detect] Semantic detection error: {e}")
    
    return jsonify({
        "success": True,
        "metadata": extracted
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

    if mode in ["pdf", "file", "document"]:
        if "file" not in files:
            return jsonify({"error": "No question document uploaded"}), 400
        file_obj = files["file"]
        question_text = extract_text_from_file(file_obj, file_obj.filename)
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
            # --- DYNAMIC CONCEPT EXPANSION BOOST ---
            concept_boost = 0.0
            if syllabus_id:
                concept_boost = concept_store.compute_concept_boost(q_text, syllabus_id)

            for d, doc, meta in zip(distances[0], docs[0], metas[0]):
                d = float(d) if d is not None else 1.0
                sem_sim = max(0.0, min(1.0, 1.0 - d))
                kw_overlap = _calculate_keyword_overlap(q_text, doc)
                
                # Hybrid score: 80% semantic, 20% exact keyword overlap
                base_sim = (sem_sim * 0.80) + (kw_overlap * 0.20)
                
                # Apply safe hybrid boosting (only if moderately high)
                applied_boost = concept_boost if base_sim > 0.60 else 0.0
                final_sim = min(1.0, base_sim + applied_boost)
                
                top_chunks.append({
                    "text":       doc,
                    "distance":   d,
                    "semantic_score": sem_sim,
                    "keyword_overlap_score": kw_overlap,
                    "concept_boost": applied_boost,
                    "similarity": final_sim,
                    "module": (
                        meta.get("module") or _extract_module(doc)
                    ) if isinstance(meta, dict) else _extract_module(doc),
                })
            
            # Re-sort chunks by new hybrid similarity
            top_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            if top_chunks:
                similarity = top_chunks[0]["similarity"]

        # Dedup → reference filter → smart relevance filter → chunk cleaner
        top_chunks = _smart_filter_chunks(_dedup_chunks(top_chunks))
        top_chunks = clean_retrieved_chunks(top_chunks)  # post-retrieval noise gate

        syllabus_meta = SYLLABI.get(syllabus_id, {}) if syllabus_id else {}

        analysis = analyze_question(
            question=q_text,
            similarity=similarity,
            threshold=threshold,
            top_chunks=top_chunks,
            co_mapper=co_mapper,
            syllabus_id=syllabus_id,
            syllabus_meta=syllabus_meta,
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
# NEW: Curriculum-driven routes
# --------------------------------------------------

@app.route("/parse_curriculum", methods=["POST"])
def parse_curriculum():
    """
    Step 1 of the new two-phase ingestion flow.

    Parse PDF/URL/text and return detected syllabus blocks WITHOUT embedding.
    Frontend displays the list so user can select which subjects to ingest.

    Form fields:
        mode   = "pdf" | "url" | "text"
        file   (if mode=pdf)
        url    (if mode=url) — JSON body
        text   (if mode=text)

    Returns:
        {
          "parse_id": "<uuid>",
          "segments": [
            {
              "syllabus_id":   "IT-VIII-PEC-IT801B",
              "department":    "Information Technology",
              "semester":      "VIII",
              "subject_name":  "Cryptography and Network Security",
              "subject_code":  "IT801B",
              "elective_type": "PEC",
              "modules":       ["Unit I: ...", ...],
              "text_preview":  "First 200 chars..."
            }, ...
          ]
        }
    """
    mode = request.form.get("mode") or (request.get_json(silent=True) or {}).get("mode", "pdf")

    if mode in ["pdf", "file", "document"]:
        if "file" not in request.files:
            return jsonify({"error": "No document uploaded"}), 400
        file_obj = request.files["file"]
        text = extract_text_from_file(file_obj, file_obj.filename)
    elif mode == "url":
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "url is required"}), 400
        try:
            text = _fetch_text_from_url(url)
        except ValueError as e:
            return jsonify({"error": str(e)}), 422
    else:
        text = request.form.get("text", "")
        if not text.strip():
            return jsonify({"error": "Empty text"}), 400

    segments = segment_curriculum(text)
    print(f"[Curriculum Parser] Detected subjects={[s['subject_name'] for s in segments]}")

    if not segments:
        return jsonify({
            "parse_id": None,
            "segments": [],
            "message": "No structured curriculum detected. Use direct ingest for single-subject text."
        })

    # Store parsed segments temporarily (keyed by parse_id)
    parse_id = str(uuid.uuid4())
    PARSED_SEGMENTS[parse_id] = segments

    # Return lightweight preview (no full text sent to frontend)
    preview = []
    for seg in segments:
        preview.append({
            "syllabus_id":           seg["syllabus_id"],
            "curriculum_department": seg["curriculum_department"],
            "subject_owner_department": seg.get("subject_owner_department"),
            "department":            seg["department"],
            "semester":              seg["semester"],
            "program":               seg.get("program"),
            "subject_name":          seg["subject_name"],
            "subject_code":          seg["subject_code"],
            "elective_type":         seg["elective_type"],
            "metadata_confidence":   seg.get("metadata_confidence"),
            "modules":               seg["modules"],
            "text_preview":          seg["syllabus_text"][:200] + "..." if len(seg["syllabus_text"]) > 200 else seg["syllabus_text"],
            "already_ingested":      vector_db.exists(seg["syllabus_id"]),
        })

    return jsonify({
        "parse_id": parse_id,
        "segments": preview,
    })


@app.route("/ingest_selected", methods=["POST"])
def ingest_selected():
    """
    Step 2 of the new two-phase ingestion flow.

    Embed ONLY the user-selected subjects from a prior /parse_curriculum call.

    JSON body:
        {
          "parse_id":      "<uuid from /parse_curriculum>",
          "syllabus_ids":  ["IT-VIII-PEC-IT801B", ...],  // subset to ingest
          "ingest_all":    false   // if true, ignores syllabus_ids and ingests all
        }

    Returns:
        {
          "ingested":           ["IT-VIII-PEC-IT801B", ...],
          "skipped_duplicates": ["IT-VII-CORE-IT701", ...]
        }
    """
    data = request.get_json(silent=True) or {}
    parse_id = data.get("parse_id", "")
    selected_ids = data.get("syllabus_ids", [])
    ingest_all = data.get("ingest_all", False)

    if not parse_id or parse_id not in PARSED_SEGMENTS:
        return jsonify({"error": "Invalid or expired parse_id. Please re-upload the curriculum."}), 400

    segments = PARSED_SEGMENTS[parse_id]

    # Filter to selected subjects (or all)
    if ingest_all:
        to_ingest = segments
    else:
        if not selected_ids:
            return jsonify({"error": "No syllabus_ids provided"}), 400
        to_ingest = [s for s in segments if s["syllabus_id"] in selected_ids]

    ingested = []
    skipped  = []
    total_chunks = 0

    for seg in to_ingest:
        sid = seg["syllabus_id"]

        # Duplicate prevention
        if vector_db.exists(sid):
            print(f"[Ingestion] Skipping duplicate: {sid}")
            # Still register in SYLLABI if not already there
            if sid not in SYLLABI:
                SYLLABI[sid] = {
                    "syllabus_id":           sid,
                    "curriculum_department":  seg["curriculum_department"],
                    "subject_owner_department": seg.get("subject_owner_department"),
                    "department":             seg["department"],
                    "semester":               seg["semester"],
                    "program":                seg.get("program"),
                    "subject_code":           seg["subject_code"],
                    "subject_name":           seg["subject_name"],
                    "elective_type":          seg["elective_type"],
                    "metadata_confidence":    seg.get("metadata_confidence"),
                    "modules":                seg["modules"],
                    "bos":                    "",
                }
            skipped.append(sid)
            continue

        # Chunk → filter references → quality gate → embed
        raw_chunks  = chunk_syllabus_with_modules(seg["syllabus_text"])
        ref_filtered = [c for c in raw_chunks if not _is_reference_entry(c[0])]
        # STEP 1-4: Pre-embedding quality gate — purge low-info metadata chunks
        clean_chunks, purged = filter_chunks_for_embedding(ref_filtered)

        if not clean_chunks:
            print(f"[Ingestion] No quality chunks for {sid} — skipping.")
            skipped.append(sid)
            continue

        print(f"[Ingestion] {sid}: {len(clean_chunks)} quality chunks ({purged} low-info purged)")

        extra_meta = {
            "curriculum_department":  seg["curriculum_department"],
            "subject_owner_department": seg.get("subject_owner_department"),
            "department":             seg["department"],
            "semester":               seg["semester"],
            "program":                seg.get("program"),
            "subject_code":           seg["subject_code"],
            "subject_name":           seg["subject_name"],
            "elective_type":          seg["elective_type"],
            "metadata_confidence":    seg.get("metadata_confidence"),
        }
        vector_db.add_syllabus(sid, clean_chunks, extra_meta=extra_meta)
        
        # Ingest dynamic curriculum concepts into ConceptStore
        try:
            concept_store.add_syllabus_concepts(sid, [c for c, _ in clean_chunks])
            print(f"[Ingestion] Extracted local concepts for {sid}")
        except Exception as e:
            print(f"[Ingestion] Failed to extract concepts for {sid}: {e}")

        SYLLABI[sid] = {
            "syllabus_id":           sid,
            "curriculum_department":  seg["curriculum_department"],
            "subject_owner_department": seg.get("subject_owner_department"),
            "department":             seg["department"],
            "semester":               seg["semester"],
            "program":                seg.get("program"),
            "subject_code":           seg["subject_code"],
            "subject_name":           seg["subject_name"],
            "elective_type":          seg["elective_type"],
            "metadata_confidence":    seg.get("metadata_confidence"),
            "modules":                seg["modules"],
            "bos":                    "",
        }
        SYLLABUS_CHUNKS[sid] = [c for c, _ in clean_chunks]
        ingested.append(sid)
        total_chunks += len(clean_chunks)
        print(f"[Ingestion] Ingested: {sid} ({len(clean_chunks)} chunks)")

    # Clean up parsed segments cache
    PARSED_SEGMENTS.pop(parse_id, None)

    return jsonify({
        "success":            True,
        "ingested":           ingested,
        "skipped_duplicates": skipped,
        "chunks_generated":   total_chunks,
    })


@app.route("/curriculum_hierarchy", methods=["GET"])
def curriculum_hierarchy():
    """
    Return the dynamic curriculum hierarchy derived from all ingested syllabi.

    Response structure:
        {
          "departments": {
            "Information Technology": {
              "VIII": [
                {
                  "syllabus_id":  "IT-VIII-PEC-IT801B",
                  "subject_name": "Cryptography and Network Security",
                  "subject_code": "IT801B",
                  "elective_type": "PEC"
                }, ...
              ]
            }
          }
        }

    This is the ONLY data source the frontend needs to build its cascading
    Department → Semester → Subject dropdowns without any static hardcoded data.
    """
    hierarchy = {}
    for s in SYLLABI.values():
        dept = s.get("curriculum_department") or s.get("department") or "Unknown"
        sem  = s.get("semester")  or "Unknown"
        if dept not in hierarchy:
            hierarchy[dept] = {}
        if sem not in hierarchy[dept]:
            hierarchy[dept][sem] = []
        hierarchy[dept][sem].append({
            "syllabus_id":           s["syllabus_id"],
            "subject_name":          s.get("subject_name", "Unknown Subject"),
            "subject_code":          s.get("subject_code", ""),
            "program":               s.get("program", ""),
            "elective_type":         s.get("elective_type", "CORE"),
            "owner_department":      s.get("subject_owner_department"),
            "metadata_confidence":   s.get("metadata_confidence", 0.7),
        })
    return jsonify({"departments": hierarchy})


@app.route("/reset_vector_db", methods=["POST"])
def reset_vector_db():
    """
    Safely wipe ALL vectors from ChromaDB and clear in-memory SYLLABI cache.
    Use this when the vector DB is polluted with bad embeddings.
    """
    vector_db.reset_collection()
    count = len(SYLLABI)
    SYLLABI.clear()
    SYLLABUS_CHUNKS.clear()
    PARSED_SEGMENTS.clear()
    return jsonify({
        "success":         True,
        "syllabi_cleared": count,
        "message":         "Vector DB reset. All embeddings removed. Please re-ingest your curriculum.",
    })


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    print("Starting Flask backend...")
    app.run(port=5000, debug=True)
