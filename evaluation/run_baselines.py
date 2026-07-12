"""
run_baselines.py
Scientific evaluation script for Syllabus Validation Baselines with Threshold Tuning.
"""

import sys
import os
import json
import csv
import re
import time
from pathlib import Path
from datetime import datetime

import requests
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# Stats & NLTK
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from statsmodels.stats.contingency_tables import mcnemar

# --- Configuration ---
_EVAL_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _EVAL_DIR.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from vectorstores.chroma_store import VectorStore
from models.embedder import Embedder

DATASET_PATH = _EVAL_DIR / "evaluation_dataset.json"
BACKEND_URL = "http://127.0.0.1:5000"

# Setup NLTK
try:
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('stopwords')
    nltk.download('wordnet')
    nltk.download('omw-1.4')

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

def preprocess_text(text):
    words = re.findall(r'\b[a-z0-9]{3,}\b', text.lower())
    words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
    return set(words)

def calc_keyword_overlap(q_set, c_set):
    if not q_set: return 0.0
    return len(q_set.intersection(c_set)) / len(q_set)

def load_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [{"question": e["question"].strip(), "expected": bool(e["expected"])} 
            for e in data if e.get("question", "").strip() and "REPLACE_ME" not in e["question"] and "expected" in e]

def discover_syllabus(backend_url):
    resp = requests.get(f"{backend_url}/list_syllabi")
    resp.raise_for_status()
    return resp.json()[0]["syllabus_id"]

def compute_metrics(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=[1, 0])
    return {
        "acc": accuracy_score(y_true, y_pred),
        "prec": precision_score(y_true, y_pred, zero_division=0),
        "rec": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "tp": int(cm[0, 0]), "fn": int(cm[0, 1]),
        "fp": int(cm[1, 0]), "tn": int(cm[1, 1])
    }

def optimize_threshold(y_true, scores):
    thresholds = np.arange(0.05, 0.96, 0.01)
    best_t = 0.05
    best_f1 = -1
    best_acc = -1
    best_fp = float('inf')
    
    for t in thresholds:
        y_pred = [1 if s >= t else 0 for s in scores]
        m = compute_metrics(y_true, y_pred)
        
        # Selection logic: Max F1 -> Max Acc -> Min FP
        if m['f1'] > best_f1:
            best_f1, best_acc, best_fp, best_t = m['f1'], m['acc'], m['fp'], t
        elif np.isclose(m['f1'], best_f1):
            if m['acc'] > best_acc:
                best_f1, best_acc, best_fp, best_t = m['f1'], m['acc'], m['fp'], t
            elif np.isclose(m['acc'], best_acc):
                if m['fp'] < best_fp:
                    best_f1, best_acc, best_fp, best_t = m['f1'], m['acc'], m['fp'], t
    return round(best_t, 2)

def main():
    print("Loading dataset...")
    dataset = load_dataset(DATASET_PATH)
    y_true = [int(r["expected"]) for r in dataset]
    
    syllabus_id = discover_syllabus(BACKEND_URL)
    print(f"Active Syllabus: {syllabus_id}")
    
    embedder = Embedder()
    vector_db = VectorStore(embed_fn=embedder.embed, persist_dir=str(_BACKEND_DIR / "data" / "vector_db"))
    
    res = vector_db.collection.get(where={"syllabus_id": syllabus_id}, include=["documents"])
    chunks = res.get("documents", [])
    if not chunks:
        print("No chunks found!")
        return

    # Precompute B1 & B2 requirements
    chunk_sets = [preprocess_text(c) for c in chunks]
    tfidf = TfidfVectorizer(stop_words='english')
    chunk_vectors = tfidf.fit_transform(chunks)
    
    # PASS 1: Score & Time
    scores = {"B1": [], "B2": [], "B3": [], "B4": [], "B5": []}
    times = {"B1": [], "B2": [], "B3": [], "B4": [], "B5": []}
    
    print("Executing Pass 1 (Scoring)...")
    for i, entry in enumerate(dataset, start=1):
        q = entry["question"]
        
        # B1
        t0 = time.perf_counter()
        q_set = preprocess_text(q)
        scores["B1"].append(max([calc_keyword_overlap(q_set, c) for c in chunk_sets]) if chunks else 0.0)
        times["B1"].append(time.perf_counter() - t0)
        
        # B2
        t0 = time.perf_counter()
        q_vec = tfidf.transform([q])
        scores["B2"].append(np.max(cosine_similarity(q_vec, chunk_vectors)) if chunks else 0.0)
        times["B2"].append(time.perf_counter() - t0)
        
        # B3
        t0 = time.perf_counter()
        sbert_res = vector_db.query(q, k=1, syllabus_id=syllabus_id)
        dists = sbert_res.get("distances")
        scores["B3"].append(1.0 - dists[0][0] if dists and dists[0] else 0.0)
        times["B3"].append(time.perf_counter() - t0)
        
        # B4 & B5
        t0 = time.perf_counter()
        payload = {"question": q, "syllabus_id": syllabus_id, "threshold": 0.0, "mode": "text"}
        try:
            api_resp = requests.post(f"{BACKEND_URL}/analyze_question", data=payload).json()
            # B4 uses the raw hybrid similarity score
            scores["B4"].append(float(api_resp.get("similarity_score", 0.0)))
            # B5 uses the final LLM boolean
            scores["B5"].append(1.0 if api_resp.get("is_in_syllabus") else 0.0)
        except Exception:
            scores["B4"].append(0.0)
            scores["B5"].append(0.0)
        times["B4"].append(time.perf_counter() - t0)
        times["B5"].append(time.perf_counter() - t0) # Share time for API call
        
        print(f"[{i}/{len(dataset)}] Scored: {q[:30]}...")

    # PASS 2: Threshold Optimization
    print("\nExecuting Pass 2 (Optimization)...")
    opt_t = {
        "B1": optimize_threshold(y_true, scores["B1"]),
        "B2": optimize_threshold(y_true, scores["B2"]),
        "B3": optimize_threshold(y_true, scores["B3"]),
        "B4": optimize_threshold(y_true, scores["B4"]),
        "B5": 0.5  # Fixed threshold for boolean
    }
    
    # Final Predictions
    preds = {k: [1 if s >= opt_t[k] else 0 for s in scores[k]] for k in scores}
    
    # Metrics
    metrics = {
        "B1": compute_metrics(y_true, preds["B1"]),
        "B2": compute_metrics(y_true, preds["B2"]),
        "B3": compute_metrics(y_true, preds["B3"]),
        "B4": compute_metrics(y_true, preds["B4"]),
        "B5": compute_metrics(y_true, preds["B5"])
    }
    
    names = {
        "B1": "Keyword Matching",
        "B2": "TF-IDF + Cosine",
        "B3": "SBERT Retrieval Only",
        "B4": "Hybrid (No Scope)",
        "B5": "Proposed (Hybrid+Scope)"
    }
    
    print("\n" + "="*60)
    print("OPTIMISED CLASSIFICATION REPORT")
    print("="*60)
    for k in ["B1", "B2", "B3", "B4", "B5"]:
        m = metrics[k]
        print(f"{names[k]} (Threshold: {opt_t[k]})")
        print(f"  TP:{m['tp']:>3} | FP:{m['fp']:>3} | TN:{m['tn']:>3} | FN:{m['fn']:>3}")
        print(f"  Acc:{m['acc']:.4f} | Prec:{m['prec']:.4f} | Rec:{m['rec']:.4f} | F1:{m['f1']:.4f}")
        print(f"  Avg Latency: {np.mean(times[k])*1000:.2f} ms")
        print("-" * 60)
        
        # Save CM
        cm_array = np.array([[m['tp'], m['fn']], [m['fp'], m['tn']]])
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(cm_array, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax)
        ax.set_title(f"Confusion Matrix: {names[k]}")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticklabels(["In Syllabus (1)", "Out of Syllabus (0)"])
        ax.set_yticklabels(["In Syllabus (1)", "Out of Syllabus (0)"])
        plt.savefig(_EVAL_DIR / f"{k}_cm.png", bbox_inches='tight')
        plt.close()

    # McNemar's Test
    best_baseline = max(["B1", "B2", "B3", "B4"], key=lambda k: metrics[k]["f1"])
    table = [[0, 0], [0, 0]]
    for i in range(len(y_true)):
        b_corr = preds[best_baseline][i] == y_true[i]
        p_corr = preds["B5"][i] == y_true[i]
        if b_corr and p_corr: table[0][0] += 1
        elif b_corr and not p_corr: table[0][1] += 1
        elif not b_corr and p_corr: table[1][0] += 1
        else: table[1][1] += 1
        
    res = mcnemar(table, exact=True)
    print(f"\nMcNemar's Test ({names[best_baseline]} vs Proposed)")
    print(f"p-value: {res.pvalue:.5f}")

    # Save CSV
    csv_path = _EVAL_DIR / "predictions_comparison.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "expected", "B1_Score", "B1_Pred", "B2_Score", "B2_Pred", "B3_Score", "B3_Pred", "B4_Score", "B4_Pred", "B5_Pred"])
        for i, q in enumerate(dataset):
            writer.writerow([
                q["question"], q["expected"],
                scores["B1"][i], preds["B1"][i],
                scores["B2"][i], preds["B2"][i],
                scores["B3"][i], preds["B3"][i],
                scores["B4"][i], preds["B4"][i],
                preds["B5"][i]
            ])
            
    # Grouped Bar Chart
    labels = list(names.values())
    acc = [metrics[k]["acc"] for k in names]
    prec = [metrics[k]["prec"] for k in names]
    rec = [metrics[k]["rec"] for k in names]
    f1 = [metrics[k]["f1"] for k in names]
    
    x = np.arange(len(labels))
    width = 0.2
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - 1.5*width, acc, width, label='Accuracy')
    ax.bar(x - 0.5*width, prec, width, label='Precision')
    ax.bar(x + 0.5*width, rec, width, label='Recall')
    ax.bar(x + 1.5*width, f1, width, label='F1 Score')
    
    ax.set_ylabel('Scores')
    ax.set_title('Evaluation Metrics by Baseline')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha='right')
    ax.legend()
    plt.tight_layout()
    plt.savefig(_EVAL_DIR / "metrics_comparison.png")
    plt.close()
    
    # Accuracy Chart
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, acc, color='skyblue')
    ax.set_ylabel('Accuracy')
    ax.set_title('Accuracy Comparison')
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.savefig(_EVAL_DIR / "accuracy_comparison.png")
    plt.close()

if __name__ == "__main__":
    main()
