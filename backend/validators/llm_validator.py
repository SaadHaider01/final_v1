import os
import re
import textwrap
from llama_cpp import Llama
from config import LLM_MODEL_PATH, LLM_RUNTIME

_llm = None

# -------------------------------
# 1. Load Local LLM Once (Singleton)
# -------------------------------
def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=os.path.abspath(LLM_MODEL_PATH),
            n_ctx=LLM_RUNTIME.get("n_ctx", 2048),
            n_threads=LLM_RUNTIME.get("n_threads", 4),
            temperature=0.0
        )
    return _llm


# -------------------------------
# 2. Extract Topics from Syllabus
# -------------------------------
GENERIC_WORDS = {
    "the", "and", "or", "of", "to", "a", "in", "on", "for", "with",
    "introduction", "importance", "overview", "basics", "concepts",
    "security", "system", "information", "data", "technology"
}

def extract_topics_from_chunks(chunks):
    """
    Automatically extracts domain-specific topics from syllabus.
    Works for ANY SUBJECT — no hardcoding.
    """
    topic_set = set()

    for c in chunks:
        text = c.get("text", "").lower()
        words = re.findall(r"[a-zA-Z]{4,}", text)  # take words >= 4 chars

        for w in words:
            if w not in GENERIC_WORDS:
                topic_set.add(w)

    return list(topic_set)


# -------------------------------
# 3. Clean & Normalize Question
# -------------------------------
def normalize_q(q):
    q = q.lower()
    q = re.sub(r"[^a-zA-Z0-9 ]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


# -------------------------------
# 4. Build LLM Prompt
# -------------------------------
def build_prompt(question, chunks, topics):
    chunk_snippets = ""
    for i, ch in enumerate(chunks[:3], start=1):
        snippet = textwrap.shorten(ch["text"].replace("\n", " "), width=200)
        chunk_snippets += f"\nCHUNK {i}: {snippet}"

    topic_list = ", ".join(topics[:15]) or "NONE"

    return f"""
You are a strict university syllabus validator.

You will receive:
1. A student's EXAM QUESTION
2. Top retrieved SYLLABUS TEXT
3. Automatically extracted SYLLABUS TOPICS

You must decide strictly:
- YES → The question is covered directly by the syllabus topics
- NO  → The question is unrelated or only loosely connected

Your output must be EXACTLY:

DECISION: YES/NO
JUSTIFICATION: <one short sentence>
MODULE: <module or 'unknown'>

---------------------------
QUESTION:
{question}

---------------------------
TOP SYLLABUS TOPICS:
{topic_list}

---------------------------
SYLLABUS CHUNKS:
{chunk_snippets}

Respond strictly in 3 lines.
""".strip()


# -------------------------------
# 5. Parse LLM Output
# -------------------------------
def parse_llm_output(raw):
    decision, justification, module = None, None, None
    lines = raw.splitlines()

    for line in lines:
        up = line.upper().strip()

        if up.startswith("DECISION:"):
            decision = line.split(":", 1)[1].strip().upper()

        elif up.startswith("JUSTIFICATION:"):
            justification = line.split(":", 1)[1].strip()

        elif up.startswith("MODULE:"):
            module = line.split(":", 1)[1].strip()

    if decision not in ("YES", "NO"):
        decision = "NO"

    if not justification:
        justification = "No justification provided."

    if not module:
        module = "unknown"

    return decision, justification, module


# -------------------------------
# 6. MAIN VALIDATOR FUNCTION
# -------------------------------
def validate_question(question_text, top_chunks):

    llm = get_llm()
    topics = extract_topics_from_chunks(top_chunks)
    norm_q = normalize_q(question_text)

    prompt = build_prompt(norm_q, top_chunks, topics)

    # Call local Llama
    resp = llm(
        prompt=prompt,
        max_tokens=120,
        temperature=0.0,
    )

    raw_text = resp.get("choices", [{}])[0].get("text", "")

    decision, justification, module = parse_llm_output(raw_text)

    return {
        "llm_decision": decision,
        "llm_justification": justification,
        "llm_module": module,
        "raw_model_text": raw_text
    }
