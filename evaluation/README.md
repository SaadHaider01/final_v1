# Evaluation Pipeline

This folder contains the complete, reproducible academic evaluation pipeline for the **AI Curriculum & Syllabus Validator**.

> **Subject-Agnostic & Curriculum-Agnostic** — Works for any department, any semester, any syllabus that is currently ingested in the backend.

---

## 📁 File Structure

```
evaluation/
│
├── run_evaluation.py        ← MAIN: Full automated evaluation pipeline
├── seed_dataset.py          ← HELPER: Interactive dataset builder
├── evaluation_dataset.json  ← TEST DATA: Your labelled question dataset
│
├── confusion_matrix.png     ← (generated) Heatmap visualization
├── results.csv              ← (generated) Per-question audit log
├── metrics.json             ← (generated) Scalar metric summary
├── false_positives.json     ← (generated) Debug: FP analysis
└── false_negatives.json     ← (generated) Debug: FN analysis
```

---

## ⚡ Quick Start

### Step 1: Install Dependencies
```bash
pip install requests scikit-learn matplotlib seaborn numpy
```

### Step 2: Ingest Your Syllabus
Make sure the Flask backend is running and at least one syllabus is ingested:
```bash
# From backend directory
python app.py
```

### Step 3: Build Your Dataset

**Option A — Manual:** Edit `evaluation_dataset.json` directly.  
Replace placeholder entries with real questions:
```json
[
  { "question": "Explain the Dining Philosophers problem.", "expected": true },
  { "question": "How does blockchain achieve decentralized consensus?", "expected": false }
]
```

**Option B — Interactive:** Run the seeder:
```bash
cd evaluation
python seed_dataset.py
```
The seeder will show you what syllabi are currently loaded, then interactively prompt you to add IN-SYLLABUS and OUT-OF-SYLLABUS questions.

### Step 4: Run the Evaluation
```bash
# From evaluation/ directory (backend must be running)
python run_evaluation.py

# Target a specific syllabus
python run_evaluation.py --syllabus IT-VIII-PEC-IT801B

# Custom dataset and threshold
python run_evaluation.py --dataset my_dataset.json --threshold 0.80
```

---

## 📊 Outputs

### `confusion_matrix.png`
Academic-style heatmap (Actual vs. Predicted) showing:
- True Positives (IN_SYLLABUS correctly accepted)
- True Negatives (OUT_OF_SYLLABUS correctly rejected)
- False Positives (OUT_OF_SYLLABUS incorrectly accepted)
- False Negatives (IN_SYLLABUS incorrectly rejected)

### `results.csv`
Per-question report with columns:

| Column | Description |
|---|---|
| `question` | Original question text |
| `expected` | Ground truth label (True/False) |
| `predicted` | Model's final `is_in_syllabus` decision |
| `similarity_score` | Final hybrid match score (0.0 – 1.0) |
| `bloom_level` | Bloom's Taxonomy cognitive level |
| `match_strength` | STRONG / PARTIAL / WEAK / NO_MATCH |
| `match_type` | DIRECT_SUBJECT / RELATED / OUT_OF_CURRICULUM |
| `is_correct` | True if predicted == expected |

### `metrics.json`
```json
{
  "accuracy":  0.93,
  "precision": 0.91,
  "recall":    0.95,
  "f1_score":  0.93,
  "tp": 35,
  "tn": 18,
  "fp": 2,
  "fn": 1,
  "total": 56,
  "timestamp": "2026-05-17T20:00:00"
}
```

### `false_positives.json` & `false_negatives.json`
Detailed debug reports listing every misclassification with:
- Similarity score
- Match strength & type
- LLM decision + justification
- Detected modules
- Diagnosis string

---

## 🔬 Evaluation Rules

1. **Final Decision Only:** Evaluation uses **only** `is_in_syllabus` from the API response.
2. **No intermediate states:** `gatekeeper_passed`, `retrieval_status`, etc. are not used for scoring.
3. **Error handling:** Questions that timeout or produce API errors are counted as **incorrect** predictions.
4. **Threshold:** Default gatekeeper threshold is `0.72`. Adjust via `--threshold`.

---

## 🎓 Dataset Guidelines

For statistically meaningful results (suitable for IEEE/research papers):

| Category | Recommended Minimum |
|---|---|
| IN-SYLLABUS (positive) questions | 20–30 |
| OUT-OF-SYLLABUS (negative) questions | 10–20 |
| Total | 30–50+ |

**Writing good OUT-OF-SYLLABUS questions:**
- Use topics from entirely different academic disciplines.
- Use specific modern applications not covered in the course (e.g., if your course is OS, ask about blockchain consensus).
- Use EXTERNAL_DOMAINS list in `grounding_validator.py` for guidance.

**Writing good IN-SYLLABUS questions:**
- Cover all course modules/units.
- Include a mix of Bloom levels: definition, explanation, comparison, design.
- Include some paraphrase variations (synonym bridging tests the Concept Store).

---

## 🛠️ CLI Reference

```
usage: run_evaluation.py [-h] [--dataset PATH] [--backend URL]
                          [--syllabus ID] [--threshold FLOAT] [--output DIR]

optional arguments:
  --dataset   PATH    Path to JSON evaluation dataset.
                      Default: evaluation/evaluation_dataset.json
  --backend   URL     Flask backend URL.
                      Default: http://127.0.0.1:5000
  --syllabus  ID      Force a specific syllabus_id.
                      Default: auto-select first available.
  --threshold FLOAT   Gatekeeper similarity threshold.
                      Default: 0.72
  --output    DIR     Output directory for all generated reports.
                      Default: evaluation/
```
