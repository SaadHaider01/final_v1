"""
generate_evaluation_dataset.py
==============================
AI-powered automatic evaluation dataset generator.

This script queries ChromaDB to fetch all ingested syllabus chunks for the active
syllabus, then utilizes your local Mistral 7B model to automatically generate
realistic in-syllabus (True) and out-of-syllabus (False) questions, writing them
directly to evaluation_dataset.json.

Eliminates all manual dataset generation work!
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Resolve paths
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"

# Add backend directory to Python path to import config and models
sys.path.append(str(_BACKEND_DIR))

try:
    import chromadb
    from llama_cpp import Llama
    import requests
except ImportError as e:
    print(f"[FATAL] Missing dependencies to run generator: {e}")
    print("        Run: pip install chromadb llama-cpp-python requests")
    sys.exit(1)

from config import LLM_MODEL_PATH, LLM_RUNTIME


def parse_args():
    p = argparse.ArgumentParser(description="AI Dataset Generator.")
    p.add_argument("--backend", default="http://127.0.0.1:5000")
    p.add_argument("--output", default=str(_SCRIPT_DIR / "evaluation_dataset.json"))
    p.add_argument("--count", type=int, default=5, help="Number of questions to generate per module.")
    return p.parse_args()


def get_active_syllabus(backend_url: str) -> str:
    """Fetch the active syllabus ID from the running Flask backend."""
    try:
        resp = requests.get(f"{backend_url}/list_syllabi", timeout=5)
        resp.raise_for_status()
        syllabi = resp.json()
        if not syllabi:
            print("[FATAL] No syllabi ingested in the backend. Please ingest a syllabus first.")
            sys.exit(1)
        return syllabi[0]["syllabus_id"]
    except Exception as e:
        print(f"[FATAL] Could not connect to running backend at {backend_url}: {e}")
        print("        Make sure your Flask backend is running (python app.py)")
        sys.exit(1)


def fetch_syllabus_chunks(syllabus_id: str, persist_dir: str = "./data/vector_db") -> dict:
    """Read the syllabus chunks grouped by module from ChromaDB."""
    db_path = _PROJECT_ROOT / "backend" / persist_dir
    client = chromadb.PersistentClient(path=str(db_path))
    try:
        collection = client.get_collection("syllabi")
    except Exception as e:
        print(f"[FATAL] Could not connect to ChromaDB collection 'syllabi': {e}")
        sys.exit(1)

    result = collection.get(where={"syllabus_id": syllabus_id})
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    if not documents:
        print(f"[FATAL] No chunks found in database for syllabus_id: {syllabus_id}")
        sys.exit(1)

    # Group chunks by module
    modules = {}
    for doc, meta in zip(documents, metadatas):
        module_name = meta.get("module") or "General Topics"
        modules.setdefault(module_name, []).append(doc)

    print(f"[ChromaDB] Fetched {len(documents)} chunks across {len(modules)} modules.")
    return modules


def generate_questions(llm: Llama, module_name: str, chunks: list, count: int) -> list:
    """Ask Mistral to generate positive and negative questions for a syllabus module."""
    snippet = "\n".join(f"- {c[:150]}" for c in chunks[:4])
    
    prompt = f"""<s>[INST] You are an expert university professor creating an exam question bank.

Syllabus Module: "{module_name}"
Syllabus Content:
{snippet}

Generate exactly {count} challenging in-syllabus exam questions that are DIRECTLY covered by this syllabus content.
Then, generate exactly {count} realistic but OUT-OF-SYLLABUS questions about related topics that are NOT covered here.

Your response MUST follow this exact format:

IN_SYLLABUS:
1. First positive question
2. Second positive question

OUT_OF_SYLLABUS:
1. First negative question
2. Second negative question
[/INST]"""

    response = llm(
        prompt,
        max_tokens=600,
        temperature=0.7,
        stop=["</s>"]
    )
    
    text = response["choices"][0]["text"]
    
    in_syllabus = []
    out_syllabus = []
    
    current_section = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "IN_SYLLABUS" in line.upper():
            current_section = "in"
            continue
        elif "OUT_OF_SYLLABUS" in line.upper():
            current_section = "out"
            continue
        
        # Parse numbered list
        if current_section and re.match(r'^\d+[\.\)]\s*', line):
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
            # Basic length guard
            if len(cleaned) > 15:
                if current_section == "in":
                    in_syllabus.append({"question": cleaned, "expected": True})
                else:
                    out_syllabus.append({"question": cleaned, "expected": False})

    # Fallbacks if parsing fails
    if not in_syllabus:
        print(f"  [Warn] Failed to parse positive questions for module {module_name}.")
    if not out_syllabus:
        print(f"  [Warn] Failed to parse negative questions for module {module_name}.")

    print(f"  Generated {len(in_syllabus)} positive & {len(out_syllabus)} negative questions for module: {module_name}")
    return in_syllabus + out_syllabus


def main():
    args = parse_args()

    print("\n" + "="*60)
    print("  AI-POWERED EVALUATION DATASET GENERATOR")
    print("="*60)

    # 1. Discover active syllabus
    syllabus_id = get_active_syllabus(args.backend)
    print(f"[Target] Active Syllabus: {syllabus_id}")

    # 2. Get syllabus chunks from ChromaDB
    modules = fetch_syllabus_chunks(syllabus_id)

    # 3. Load local LLM
    model_path = _PROJECT_ROOT / "backend" / "models" / Path(LLM_MODEL_PATH).name
    if not model_path.exists():
        print(f"[FATAL] Local model file not found at: {model_path}")
        sys.exit(1)

    print(f"[LLM] Loading Mistral model: {model_path.name}")
    llm = Llama(
        model_path=str(model_path),
        n_ctx=2048,
        n_threads=LLM_RUNTIME.get("n_threads", 4),
        n_gpu_layers=LLM_RUNTIME.get("n_gpu_layers", 0),
        temperature=0.7,
        verbose=False,
    )

    # 4. Generate questions for each module
    all_dataset = []
    for mod_name, chunks in modules.items():
        # Clean module title for prompt readability
        cleaned_name = re.sub(r'^(Unit|Module)\s+\d+[\s\.\:]*', '', mod_name).strip()
        questions = generate_questions(llm, cleaned_name, chunks, args.count)
        all_dataset.extend(questions)

    if not all_dataset:
        print("[FATAL] No questions generated.")
        sys.exit(1)

    # 5. Save dataset
    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_dataset, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"[Saved] Automatically generated {len(all_dataset)} test questions!")
    print(f"[File ] {out_path}")
    print(f"        You can now run: python run_evaluation.py")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import re
    main()
