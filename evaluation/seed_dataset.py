"""
seed_dataset.py
===============
Interactive helper to build a subject-agnostic evaluation_dataset.json.

Run this script AFTER ingesting your syllabus into the backend.
It will:
    1. Query /curriculum_hierarchy to show you what is currently loaded.
    2. Interactively prompt you to add IN-SYLLABUS and OUT-OF-SYLLABUS questions.
    3. Write (or append to) evaluation_dataset.json.

Usage:
    python seed_dataset.py
    python seed_dataset.py --backend http://127.0.0.1:5000
    python seed_dataset.py --output my_custom_dataset.json
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[FATAL] 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

_SCRIPT_DIR   = Path(__file__).resolve().parent
DEFAULT_OUTPUT = _SCRIPT_DIR / "evaluation_dataset.json"
DEFAULT_BACKEND = "http://127.0.0.1:5000"


def parse_args():
    p = argparse.ArgumentParser(description="Interactive evaluation dataset builder.")
    p.add_argument("--backend", default=DEFAULT_BACKEND)
    p.add_argument("--output",  default=str(DEFAULT_OUTPUT))
    return p.parse_args()


def fetch_hierarchy(backend_url: str) -> dict:
    try:
        resp = requests.get(f"{backend_url}/curriculum_hierarchy", timeout=10)
        resp.raise_for_status()
        return resp.json().get("departments", {})
    except requests.exceptions.ConnectionError:
        print(f"[WARN] Could not reach backend at {backend_url}. Continuing without hierarchy.")
        return {}
    except Exception as e:
        print(f"[WARN] Hierarchy fetch failed: {e}")
        return {}


def display_hierarchy(hierarchy: dict):
    if not hierarchy:
        print("  (No hierarchy data available — make sure a syllabus is ingested.)")
        return
    print("\n  Currently Loaded Curriculum:")
    print("  " + "-"*50)
    for dept, semesters in hierarchy.items():
        print(f"  Department: {dept}")
        for sem, subjects in semesters.items():
            print(f"    Semester {sem}:")
            for subj in subjects:
                print(f"      [{subj.get('elective_type','?')}] "
                      f"{subj.get('subject_name','?')} "
                      f"({subj.get('subject_code','?')})")
    print("  " + "-"*50 + "\n")


def collect_questions(label: str, expected: bool) -> list:
    """Interactively collect questions with a given expected label."""
    entries = []
    print(f"\n  Enter questions that are {'INSIDE' if expected else 'OUTSIDE'} the syllabus.")
    print(f"  (Type 'done' on a blank line when finished.)\n")
    idx = 1
    while True:
        q = input(f"  [{label}] Q{idx}: ").strip()
        if q.lower() == "done" or q == "":
            if q.lower() == "done":
                break
            # Empty line — ask for confirmation
            confirm = input("  No question entered. Type 'done' to finish or press Enter to try again: ").strip()
            if confirm.lower() == "done":
                break
            continue
        entries.append({"question": q, "expected": expected})
        idx += 1
    return entries


def main():
    args = parse_args()

    print("\n" + "="*60)
    print("  EVALUATION DATASET SEEDER")
    print("  AI Curriculum & Syllabus Validator")
    print("="*60)

    # Show loaded curriculum
    hierarchy = fetch_hierarchy(args.backend)
    display_hierarchy(hierarchy)

    entries = []

    # Collect IN-SYLLABUS questions
    in_syllabus = collect_questions("IN-SYLLABUS", expected=True)
    entries.extend(in_syllabus)

    # Collect OUT-OF-SYLLABUS questions
    out_syllabus = collect_questions("OUT-OF-SYLLABUS", expected=False)
    entries.extend(out_syllabus)

    if not entries:
        print("\n[WARN] No entries collected. Dataset not saved.")
        return

    # Load existing dataset if it exists (append mode)
    out_path = Path(args.output)
    existing = []
    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                # Filter out placeholder entries
                existing = [e for e in existing if "REPLACE_ME" not in e.get("question", "")]
            print(f"\n[Info] Loaded {len(existing)} existing entries from {out_path.name}.")
        except Exception:
            existing = []

    merged = existing + entries

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"\n[Saved] {len(entries)} new entries added. Total: {len(merged)} entries.")
    print(f"[File ] {out_path}")
    print(f"\n  Run evaluation with:")
    print(f"  python run_evaluation.py --dataset {out_path}\n")


if __name__ == "__main__":
    main()
