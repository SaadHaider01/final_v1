# AI-Powered Curriculum & Syllabus Validator

A robust, research-oriented system designed to validate academic assessment questions against institutional syllabi. The system uses a hybrid architecture combining semantic vector search, deterministic heuristic gating, and Large Language Model (LLM) reasoning to ensure academic integrity, detect question modules, classify Bloom's taxonomy levels, and map Course Outcomes (COs) and Program Outcomes (POs).

## Tech Stack & Models Used

### Models
- **Embeddings:** `intfloat/multilingual-e5-base` (via `SentenceTransformers`) for projecting syllabus chunks into high-dimensional vector space.
- **LLM Reasoning:** Mistral 7B (or similar local Llama-based models) for offline validation and academic grounding.

### Technology Stack
- **Backend:** Python, Flask
- **Frontend:** React
- **Vector Database:** ChromaDB (Persistent local storage)
- **Document Processing:** `pypdf` for PDF content extraction

## System Architecture

The project consists of a Python/Flask backend and a React frontend. The backend operates entirely on offline, privacy-preserving open-source models, mitigating data leakage and recurring API costs.

### 1. Ingestion Pipeline & Metadata Persistence
- **Content Extraction:** Processes raw syllabus data from three sources: PDF documents (via `pypdf`), direct URL scraping (HTML/PDF), or dynamic modular text-pasting.
- **Smart Text Chunking:** Employs a regex-driven chunking strategy (`processors/text_chunker.py`) that respects structural integrity. It detects both keyword-based module headings (e.g., "Module 1", "UNIT II") and bare-number table formats (e.g., "1  Introduction: ...") common in university curriculum documents.
- **Hierarchical Metadata Validation:** Institutional data is modeled using a strict hierarchy (*Board of Studies → Department → Program → Semester → Subject*). This normalises the semantic search space and prevents namespace collisions across different university degrees.

### 2. Semantic Search & Vector Storage (ChromaDB)
- **Local Embedding Engine:** Utilises `SentenceTransformers` to project syllabus chunks into high-dimensional vector space.
- **Metadata-Enriched Collections:** ChromaDB stores not only the embedded text but also the extracted module numbers and the hierarchical institutional metadata (BOS, Dept, Sem, Subject).
- **Cosine Gatekeeping:** A deterministic cosine similarity threshold is applied to retrieved chunks. This acts as a primary filter, blocking entirely irrelevant questions before they reach the computationally expensive LLM reasoning phase.

### 3. Curriculum Enrichment Engine
The system performs multi-dimensional analysis on each queried question without requiring extra LLM calls, making it highly efficient for batch processing:

* **Bloom's Taxonomy Classification (Hybrid Model):**
  Uses a descending-order rule-based model (`services/bloom_classifier.py`) separated into two passes:
  1. *Action Verb Detection:* Matches cognitive triggers (e.g., "design" → Create, "compare" → Analyze).
  2. *WH-Question Pattern Matching:* Detects structural exam questions (e.g., "What are the types of..." → Understand).
* **Multi-Module Detection:**
  Cross-references retrieved semantic chunks against stored module metadata. It detects when a single compound question spans multiple academic modules (e.g., querying across `k=5` nearest neighbours).
* **Outcome Mapping (CO / PO):**
  Dynamically maps evaluated questions to stored Course Outcomes (COs) using semantic proximity, and subsequently derives the associated Program Outcomes (POs/PCOs) through a deterministic relationship dictionary.

### 4. LLM Reasoning Agent
Questions that pass the cosine gatekeeper are formulated into a concise prompt alongside the $k$-nearest syllabus chunks. A local LLM (e.g., Mistral/Llama) validates if the question is academically grounded within the retrieved context, returning a structured JSON containing a definitive 'YES/NO' decision and a rationalised justification.

## Frontend Client 

The React-based client (`frontend/src/`) provides an interactive interface for institutional users:
- **Cascading Ingestion Form:** Enforces the BOS → Dept → Program → Sem metadata hierarchy, allowing users to upload multiple subjects rapidly without re-entering unchanged hierarchical data.
- **Dynamic Module Input:** The Text Paste mode provides dynamic input rows, automatically formatting user input into the numbered format required by the backend chunker.
- **Interactive Playground:** Supports both single-question deep dives and batch processing (e.g., full exam paper uploads). Visualises cosine similarity charts, Bloom classification badges, mapped outcomes, and LLM reasoning steps in real-time.

## Research & Pedagogical Implications

This system is engineered to solve key challenges in academic administration:
1. **Automation of Curriculum Auditing:** Replaces manual syllabus-mapping, reducing human error in outcome-based education (OBE) compliance.
2. **Quality Assurance:** Assesses the cognitive spread of exam papers by aggregating Bloom's taxonomy classifications across an entire batch of questions.
3. **Out-of-Syllabus Detection:** The deterministic gatekeeper prevents hallucination or over-permissive LLM judgements by enforcing a strict mathematical baseline for semantic relevance.
4. **Institutional Scalability:** The metadata architecture is designed to manage the complexity of full university deployments, where hundreds of subjects share similar terminology but apply to different departments or programs.