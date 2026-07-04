"""
run_evaluation.py
=================
Automated evaluation pipeline for the AI Curriculum & Syllabus Validator.

This script is 100% subject-agnostic, curriculum-agnostic, and ingestion-agnostic.
It evaluates whatever syllabus is currently loaded in the running backend.

Pipeline:
    1. Load evaluation_dataset.json
    2. Discover the active syllabus_id from the live backend
    3. Send each question through the /analyze_question endpoint
    4. Collect: predicted, similarity_score, bloom_level, match_strength, match_type
    5. Compute: TP / TN / FP / FN + Accuracy / Precision / Recall / F1
    6. Save: evaluation/confusion_matrix.png
    7. Save: evaluation/results.csv
    8. Save: evaluation/metrics.json
    9. Print: false_positives.json + false_negatives.json (debug)

Usage:
    # Make sure Flask backend is running on http://127.0.0.1:5000
    python run_evaluation.py [OPTIONS]

Options:
    --dataset  PATH     Path to evaluation JSON file
                        Default: evaluation_dataset.json (auto-resolved)
    --backend  URL      Backend base URL
                        Default: http://127.0.0.1:5000
    --syllabus ID       Force a specific syllabus_id (optional)
                        If omitted, the first available syllabus is auto-selected.
    --threshold FLOAT   Similarity threshold (default: 0.72)
    --output   DIR      Output directory for reports
                        Default: evaluation/

Example:
    python run_evaluation.py
    python run_evaluation.py --syllabus IT-VIII-PEC-IT801B
    python run_evaluation.py --dataset my_questions.json --threshold 0.80
"""

import sys
import os
import json
import argparse
import csv
import re
from pathlib import Path
from datetime import datetime

# ── Third-party ─────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("[FATAL] 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

try:
    import numpy as np
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        confusion_matrix
    )
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend (safe for CI / server)
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import seaborn as sns
except ImportError as e:
    print(f"[FATAL] Missing dependency: {e}")
    print("Run: pip install scikit-learn matplotlib seaborn numpy")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Constants & defaults
# ─────────────────────────────────────────────────────────────────────────────

# Resolve paths relative to THIS script's location
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent                  # d:/final_v1
_EVAL_DIR     = _SCRIPT_DIR                         # d:/final_v1/evaluation/

DEFAULT_DATASET   = _EVAL_DIR / "evaluation_dataset.json"
DEFAULT_BACKEND   = "http://127.0.0.1:5000"
DEFAULT_THRESHOLD = 0.72
DEFAULT_OUTPUT    = _EVAL_DIR


# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Automated evaluation pipeline for the AI Syllabus Validator."
    )
    p.add_argument("--dataset",   default=str(DEFAULT_DATASET),   help="Path to evaluation JSON dataset.")
    p.add_argument("--backend",   default=DEFAULT_BACKEND,         help="Flask backend base URL.")
    p.add_argument("--syllabus",  default=None,                    help="Force a specific syllabus_id.")
    p.add_argument("--threshold", default=DEFAULT_THRESHOLD, type=float, help="Similarity gatekeeper threshold.")
    p.add_argument("--output",    default=str(DEFAULT_OUTPUT),     help="Output directory for reports.")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Load dataset
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset(path: str) -> list:
    """
    Load evaluation_dataset.json.
    Each entry must have:
        question  (str)  — the exam question text
        expected  (bool) — True if it should be IN syllabus, False otherwise
    Entries with placeholder text ("REPLACE_ME") are automatically skipped.
    """
    p = Path(path)
    if not p.exists():
        print(f"[FATAL] Dataset not found: {path}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or not data:
        print("[FATAL] Dataset must be a non-empty JSON array.")
        sys.exit(1)

    # Filter out placeholder entries
    real_entries = []
    skipped = 0
    for i, entry in enumerate(data):
        q = entry.get("question", "").strip()
        if "REPLACE_ME" in q or not q:
            skipped += 1
            continue
        if "expected" not in entry:
            print(f"[WARN] Entry {i} is missing 'expected' field — skipping.")
            skipped += 1
            continue
        real_entries.append({
            "question": q,
            "expected": bool(entry["expected"]),
        })

    if skipped:
        print(f"[Dataset] {skipped} placeholder / incomplete entries skipped.")
    if not real_entries:
        print("[FATAL] No valid entries in dataset. Please replace placeholder questions.")
        sys.exit(1)

    print(f"[Dataset] Loaded {len(real_entries)} valid evaluation entries.")
    return real_entries


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Discover active syllabus_id
# ─────────────────────────────────────────────────────────────────────────────

def discover_syllabus(backend_url: str, forced_id: str = None) -> str:
    """
    Auto-detect the first available syllabus from /list_syllabi.
    If forced_id is provided, it is returned directly (after validating it exists).
    """
    try:
        resp = requests.get(f"{backend_url}/list_syllabi", timeout=10)
        resp.raise_for_status()
        syllabi = resp.json()
    except requests.exceptions.ConnectionError:
        print(f"[FATAL] Cannot connect to backend at {backend_url}.")
        print("        Make sure the Flask server is running: python app.py")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] Could not query /list_syllabi: {e}")
        sys.exit(1)

    if not syllabi:
        print("[FATAL] No syllabi are currently loaded in the backend.")
        print("        Please ingest a syllabus before running evaluation.")
        sys.exit(1)

    if forced_id:
        ids = [s["syllabus_id"] for s in syllabi]
        if forced_id not in ids:
            print(f"[FATAL] Forced syllabus_id '{forced_id}' not found in backend.")
            print(f"        Available IDs: {ids}")
            sys.exit(1)
        print(f"[Syllabus] Using forced syllabus_id: {forced_id}")
        return forced_id

    # Auto-select first available
    selected = syllabi[0]["syllabus_id"]
    subject  = syllabi[0].get("subject_name", "Unknown Subject")
    dept     = syllabi[0].get("curriculum_department") or syllabi[0].get("department", "Unknown")
    sem      = syllabi[0].get("semester", "?")
    print(f"[Syllabus] Auto-selected: {selected}")
    print(f"           Subject: {subject} | Department: {dept} | Semester: {sem}")
    if len(syllabi) > 1:
        print(f"           ({len(syllabi) - 1} other syllabus entries available. "
              f"Use --syllabus <id> to target a specific one.)")
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Query /analyze_question for a single question
# ─────────────────────────────────────────────────────────────────────────────

def analyze_question(
    question: str,
    syllabus_id: str,
    threshold: float,
    backend_url: str,
) -> dict:
    """
    POST to /analyze_question and return the structured result dict.
    Handles network errors gracefully with a sentinel error record.
    """
    payload = {
        "question":    question,
        "syllabus_id": syllabus_id,
        "threshold":   threshold,
        "mode":        "text",
    }
    try:
        resp = requests.post(
            f"{backend_url}/analyze_question",
            data=payload,
            timeout=120,  # LLM inference can be slow on CPU
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"  [TIMEOUT] Question timed out after 120s — marking as error.")
        return {"_error": "timeout", "is_in_syllabus": False, "similarity_score": 0.0}
    except Exception as e:
        print(f"  [ERROR] Request failed: {e}")
        return {"_error": str(e), "is_in_syllabus": False, "similarity_score": 0.0}


# ─────────────────────────────────────────────────────────────────────────────
# Step 3B — Run the full evaluation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation_loop(
    dataset:     list,
    syllabus_id: str,
    threshold:   float,
    backend_url: str,
) -> list:
    """
    Send every question through the backend and return a list of result records.
    Each record contains the full API response merged with expected ground truth.
    """
    results = []
    total   = len(dataset)

    print(f"\n{'='*60}")
    print(f"  Running evaluation: {total} questions → syllabus {syllabus_id}")
    print(f"{'='*60}")

    for i, entry in enumerate(dataset, start=1):
        question = entry["question"]
        expected = entry["expected"]

        short_q  = question[:70] + "..." if len(question) > 70 else question
        print(f"  [{i:>3}/{total}] {short_q}")

        api_resp = analyze_question(question, syllabus_id, threshold, backend_url)

        is_error   = "_error" in api_resp
        predicted  = bool(api_resp.get("is_in_syllabus", False))
        sim_score  = float(api_resp.get("similarity_score", 0.0))
        bloom      = api_resp.get("bloom_level", "Unknown")
        match_str  = api_resp.get("match_strength", "NO_MATCH")
        match_type = api_resp.get("match_type", "OUT_OF_CURRICULUM")
        is_correct = (not is_error) and (predicted == expected)

        status_icon = "✓" if is_correct else "✗"
        error_note  = f" [ERROR: {api_resp['_error']}]" if is_error else ""
        print(f"         {status_icon} expected={expected} predicted={predicted} "
              f"sim={sim_score:.4f} bloom={bloom}{error_note}")

        results.append({
            "question":        question,
            "expected":        expected,
            "predicted":       predicted,
            "similarity_score": sim_score,
            "bloom_level":     bloom,
            "match_strength":  match_str,
            "match_type":      match_type,
            "is_correct":      is_correct,
            "is_error":        is_error,
            "error_detail":    api_resp.get("_error", ""),
            # Preserve full API extras for debug
            "_llm_decision":   api_resp.get("llm_decision", ""),
            "_llm_justification": api_resp.get("llm_justification", ""),
            "_modules_detected": str(api_resp.get("modules_detected", [])),
        })

    errored = sum(1 for r in results if r["is_error"])
    if errored:
        print(f"\n[WARN] {errored} questions produced API errors (counted as incorrect).")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 & 5 — Compute confusion matrix & classification metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(results: list) -> dict:
    """
    Compute TP/TN/FP/FN and sklearn classification metrics.
    Uses ONLY the final is_in_syllabus boolean — no intermediate state.
    """
    y_true = [int(r["expected"])  for r in results]
    y_pred = [int(r["predicted"]) for r in results]

    # Confusion matrix values
    cm     = confusion_matrix(y_true, y_pred, labels=[1, 0])
    tp     = int(cm[0, 0])   # expected=True,  predicted=True
    fn     = int(cm[0, 1])   # expected=True,  predicted=False
    fp     = int(cm[1, 0])   # expected=False, predicted=True
    tn     = int(cm[1, 1])   # expected=False, predicted=False

    # Handle edge cases (all predicted same class)
    zero_div = "warn"
    acc  = round(float(accuracy_score(y_true, y_pred)), 4)
    prec = round(float(precision_score(y_true, y_pred, zero_division=0)), 4)
    rec  = round(float(recall_score(y_true, y_pred, zero_division=0)), 4)
    f1   = round(float(f1_score(y_true, y_pred, zero_division=0)), 4)

    metrics = {
        "accuracy":  acc,
        "precision": prec,
        "recall":    rec,
        "f1_score":  f1,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "total":           len(results),
        "errors_skipped":  sum(1 for r in results if r["is_error"]),
        "timestamp":       datetime.now().isoformat(timespec="seconds"),
    }

    print(f"\n{'='*60}")
    print(f"  EVALUATION METRICS")
    print(f"{'='*60}")
    print(f"  Total questions : {metrics['total']}")
    print(f"  True Positives  : {tp}   (in-syllabus correctly identified)")
    print(f"  True Negatives  : {tn}   (out-of-syllabus correctly rejected)")
    print(f"  False Positives : {fp}   (out-of-syllabus incorrectly accepted)")
    print(f"  False Negatives : {fn}   (in-syllabus incorrectly rejected)")
    print(f"  ─────────────────────────────────────────")
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {prec:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1-Score  : {f1:.4f}")
    print(f"{'='*60}\n")

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Generate Confusion Matrix Heatmap PNG
# ─────────────────────────────────────────────────────────────────────────────

def save_confusion_matrix_png(metrics: dict, output_dir: Path):
    """
    Generate a clean, academic-style confusion matrix heatmap.
    Saved as: <output_dir>/confusion_matrix.png
    """
    tp = metrics["tp"]
    tn = metrics["tn"]
    fp = metrics["fp"]
    fn = metrics["fn"]

    # Layout: rows=Actual, cols=Predicted  |  [TP, FN] / [FP, TN]
    cm_array = np.array([[tp, fn], [fp, tn]])

    fig, ax = plt.subplots(figsize=(7, 5.5))

    # Academic color palette (blue-white)
    cmap = sns.color_palette("Blues", as_cmap=True)

    sns.heatmap(
        cm_array,
        annot=False,        # We draw custom annotations below
        fmt="d",
        cmap=cmap,
        linewidths=0.8,
        linecolor="#cccccc",
        cbar=True,
        ax=ax,
    )

    # Custom cell annotations (value + label)
    cell_labels = [
        (0, 0, tp, "True Positive",  "white",  "✓"),
        (0, 1, fn, "False Negative", "#1a1a1a", "✗"),
        (1, 0, fp, "False Positive", "#1a1a1a", "✗"),
        (1, 1, tn, "True Negative",  "white",  "✓"),
    ]
    for row, col, val, label, txt_color, icon in cell_labels:
        ax.text(
            col + 0.5, row + 0.38,
            f"{icon}  {val}",
            ha="center", va="center",
            fontsize=22, fontweight="bold", color=txt_color,
        )
        ax.text(
            col + 0.5, row + 0.68,
            label,
            ha="center", va="center",
            fontsize=8.5, color=txt_color, alpha=0.85,
        )

    # Axis labels
    ax.set_xlabel("Predicted Label", fontsize=12, labelpad=12, fontweight="bold")
    ax.set_ylabel("Actual Label",    fontsize=12, labelpad=12, fontweight="bold")
    ax.set_xticklabels(["IN_SYLLABUS", "OUT_OF_SYLLABUS"], fontsize=10)
    ax.set_yticklabels(["IN_SYLLABUS", "OUT_OF_SYLLABUS"], fontsize=10, rotation=0)

    # Title block
    f1    = metrics["f1_score"]
    acc   = metrics["accuracy"]
    prec  = metrics["precision"]
    rec   = metrics["recall"]
    total = metrics["total"]

    ax.set_title(
        f"AI Syllabus Validator — Confusion Matrix\n"
        f"Accuracy={acc:.2%}  Precision={prec:.2%}  Recall={rec:.2%}  F1={f1:.2%}  "
        f"(n={total})",
        fontsize=10.5, pad=16, color="#222222"
    )

    plt.tight_layout()

    out_path = output_dir / "confusion_matrix.png"
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close()

    print(f"[Output] Confusion matrix saved → {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Save results.csv
# ─────────────────────────────────────────────────────────────────────────────

def save_results_csv(results: list, output_dir: Path):
    """
    Write the per-question evaluation report to results.csv.
    Columns match the specification exactly.
    """
    out_path = output_dir / "results.csv"
    fieldnames = [
        "question", "expected", "predicted",
        "similarity_score", "bloom_level",
        "match_strength", "match_type", "is_correct",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"[Output] Results CSV saved     → {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Save metrics.json
# ─────────────────────────────────────────────────────────────────────────────

def save_metrics_json(metrics: dict, output_dir: Path):
    """Write the scalar metrics summary to metrics.json."""
    out_path = output_dir / "metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Output] Metrics JSON saved    → {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Bonus Step — False Positive / False Negative debug reports
# ─────────────────────────────────────────────────────────────────────────────

def save_debug_reports(results: list, output_dir: Path):
    """
    Write false_positives.json and false_negatives.json for retrieval debugging.
    These are invaluable for understanding where the hybrid pipeline breaks.
    """
    false_positives = [
        {
            "question":        r["question"],
            "similarity_score": r["similarity_score"],
            "match_strength":  r["match_strength"],
            "match_type":      r["match_type"],
            "bloom_level":     r["bloom_level"],
            "llm_decision":    r["_llm_decision"],
            "llm_justification": r["_llm_justification"],
            "modules_detected": r["_modules_detected"],
            "diagnosis":       "OUT-OF-SYLLABUS question was incorrectly ACCEPTED.",
        }
        for r in results
        if not r["expected"] and r["predicted"]
    ]

    false_negatives = [
        {
            "question":        r["question"],
            "similarity_score": r["similarity_score"],
            "match_strength":  r["match_strength"],
            "match_type":      r["match_type"],
            "bloom_level":     r["bloom_level"],
            "llm_decision":    r["_llm_decision"],
            "llm_justification": r["_llm_justification"],
            "modules_detected": r["_modules_detected"],
            "diagnosis":       "IN-SYLLABUS question was incorrectly REJECTED.",
        }
        for r in results
        if r["expected"] and not r["predicted"]
    ]

    fp_path = output_dir / "false_positives.json"
    fn_path = output_dir / "false_negatives.json"

    with open(fp_path, "w", encoding="utf-8") as f:
        json.dump(false_positives, f, indent=2)

    with open(fn_path, "w", encoding="utf-8") as f:
        json.dump(false_negatives, f, indent=2)

    fp_count = len(false_positives)
    fn_count = len(false_negatives)

    print(f"[Debug ] False Positives ({fp_count}) → {fp_path}")
    print(f"[Debug ] False Negatives ({fn_count}) → {fn_path}")

    if false_positives:
        print("\n  ── False Positives (model accepted an out-of-scope question) ──")
        for item in false_positives:
            print(f"  • {item['question'][:100]}")
            print(f"    Sim={item['similarity_score']:.4f}  "
                  f"Strength={item['match_strength']}  LLM={item['llm_decision']}")

    if false_negatives:
        print("\n  ── False Negatives (model rejected an in-scope question) ──")
        for item in false_negatives:
            print(f"  • {item['question'][:100]}")
            print(f"    Sim={item['similarity_score']:.4f}  "
                  f"Strength={item['match_strength']}  LLM={item['llm_decision']}")
            print(f"    Reason: {item['llm_justification']}")

    return fp_path, fn_path


# ─────────────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("  AI SYLLABUS VALIDATOR — EVALUATION PIPELINE")
    print("="*60)
    print(f"  Dataset   : {args.dataset}")
    print(f"  Backend   : {args.backend}")
    print(f"  Threshold : {args.threshold}")
    print(f"  Output    : {output_dir}")
    print("="*60 + "\n")

    # ── Step 1: Load dataset ─────────────────────────────────────────────────
    dataset = load_dataset(args.dataset)

    # ── Step 2: Discover syllabus_id ─────────────────────────────────────────
    syllabus_id = discover_syllabus(args.backend, forced_id=args.syllabus)

    # ── Step 3: Run evaluation loop ──────────────────────────────────────────
    results = run_evaluation_loop(
        dataset     = dataset,
        syllabus_id = syllabus_id,
        threshold   = args.threshold,
        backend_url = args.backend,
    )

    # ── Step 4 & 5: Compute metrics ──────────────────────────────────────────
    metrics = compute_metrics(results)

    # ── Step 6: Confusion matrix PNG ─────────────────────────────────────────
    save_confusion_matrix_png(metrics, output_dir)

    # ── Step 7: CSV report ───────────────────────────────────────────────────
    save_results_csv(results, output_dir)

    # ── Step 8: Metrics JSON ─────────────────────────────────────────────────
    save_metrics_json(metrics, output_dir)

    # ── Bonus: Debug reports ─────────────────────────────────────────────────
    save_debug_reports(results, output_dir)

    print(f"\n{'='*60}")
    print(f"  Evaluation complete.  All outputs saved to: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
