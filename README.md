# AI Curriculum & Syllabus Validator

## 🚀 What it does
A system that automatically validates whether exam questions belong to a syllabus module and classifies their complexity using Bloom’s taxonomy.

## 💡 Why it matters
Manual syllabus validation is slow, inconsistent, and error-prone.  
This system reduces verification time and improves accuracy using a hybrid AI + rule-based approach, ensuring fair and consistent academic evaluation.

---

## 🧠 System Overview

This project is built as a **hybrid AI system** combining:
- Semantic vector search for retrieval
- Deterministic filtering for reliability
- LLM reasoning for contextual validation

Unlike naive LLM-only solutions, this system prioritizes **accuracy, consistency, and cost-efficiency**.

---

## 🏗️ Architecture

- **Frontend:** React (interactive validation UI)
- **Backend:** Python (Flask)
- **Vector DB:** ChromaDB
- **Embeddings:** SentenceTransformers (`multilingual-e5-base`)
- **LLM:** Mistral 7B (local inference via llama-cpp)
- **Document Processing:** pypdf

---

## ⚙️ How it works

1. **Ingestion**
   - Extract syllabus from PDF / URL / text
   - Chunk content intelligently using structure-aware parsing
   - Store embeddings + metadata in ChromaDB

2. **Retrieval**
   - Convert query into embeddings
   - Fetch top-k relevant syllabus chunks using cosine similarity

3. **Filtering (Key Step)**
   - Apply similarity threshold to reject irrelevant queries early  
   - Prevents unnecessary LLM usage and reduces hallucinations

4. **Enrichment**
   - Bloom’s taxonomy classification (rule-based)
   - Multi-module detection
   - CO/PO mapping

5. **LLM Validation**
   - Final reasoning using contextual syllabus data
   - Returns structured YES/NO + justification

---

## 📊 Results
- ~85% accuracy in syllabus-question validation
- Significant reduction in manual verification effort
- Improved consistency across academic evaluations

---

## 🧩 Engineering Decisions

- **Hybrid pipeline (not LLM-only):**  
  Used embedding-based retrieval + rule-based filtering before LLM to improve reliability

- **Similarity threshold gating:**  
  Prevents irrelevant queries from reaching the LLM → faster + cheaper + more accurate

- **Modular backend design:**  
  Core logic split into independent services (classification, mapping, validation) for scalability

---

## ⚠️ Challenges & Learnings

- Handling **unstructured syllabus formats** (PDF inconsistencies)
- Balancing **accuracy vs false positives** in validation
- Preventing **LLM hallucination** using deterministic filtering
- Maintaining **retrieval quality** with noisy academic data

---

## 🔮 Future Improvements

- OCR support for scanned syllabus documents
- Fine-tuned lightweight model for faster inference
- Admin dashboards for institutional-level analytics

---

## 🧠 Key Takeaway

This project is not just about using AI —  
it’s about **designing a reliable system around AI**.
