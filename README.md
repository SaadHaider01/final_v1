# AI-Powered Curriculum & Syllabus Validator

## What it does
The system validates academic assessment questions against institutional syllabi to ensure curriculum alignment. It automates syllabus mapping by analyzing exam questions to determine if they are in the syllabus, classifying their Bloom's taxonomy levels, and mapping them to specific Course and Program Outcomes.

## Why it matters
This system automates manual curriculum auditing, significantly reducing human error in outcome-based education (OBE) compliance. It guarantees quality assurance by assessing the cognitive spread of exam papers and prevents out-of-syllabus questions from making their way into final academic assessments, ensuring fairness for students.

## Architecture
The system uses a hybrid architecture combining a React frontend for institutional ingestion and a Python/Flask backend. The backend utilizes semantic vector search (ChromaDB) to retrieve relevant syllabus contexts, deterministic heuristic gating (Cosine Similarity) to filter irrelevant questions quickly, and local Large Language Model (Mistral 7B) reasoning to validate complex application-level questions entirely offline.

## Tech Stack
- **Backend:** Python, Flask
- **Frontend:** React
- **Vector Database:** ChromaDB (Persistent local storage)
- **Embeddings:** `intfloat/multilingual-e5-base` (via `SentenceTransformers`)
- **LLM Reasoning:** Mistral 7B (via `llama-cpp-python`)
- **Document Processing:** `pypdf`

## How it works
1. **Ingestion & Metadata Persistence:** Syllabi (via PDF, Text, or URL) are uploaded, intelligently chunked respecting structural integrity, and stored in ChromaDB along with a strict institutional metadata hierarchy (Board of Studies → Dept → Program → Sem → Subject).
2. **Vector Retrieval:** User exam questions are embedded, and the backend retrieves the top $k$-nearest syllabus chunks using Cosine Similarity.
3. **Gateway Filtering:** A rigorous deterministic similarity threshold acts as a gatekeeper, instantly rejecting highly irrelevant questions to save compute resources.
4. **Curriculum Enrichment:** Passing questions undergo fast, rule-based processing for hybrid Bloom's Taxonomy Classification, Multi-Module detection, and CO/PO outcome mapping.
5. **LLM Validation:** Borderline and passing questions are bundled with their relevant syllabus chunks and sent to a local LLM to contextually rationalize and definitively validate if the question is academically grounded.

## Key Challenges
- **Semantic Ambiguity:** Resolving cross-domain terminology conflicts required implementing strict hierarchical metadata namespaces to sandbox and isolate vector searches between different university degrees.
- **Complex Layout Parsing:** Extracting structured module markers (e.g. "UNIT II") versus unstructured bare-number tables (common in university PDFs) required developing extremely robust, multi-format regular expressions prior to vectorization.
- **Batch Processing Deduplication:** Handling redundant or closely-matched syllabus text required aggressive backend text deduplication to maintain high retrieval quality without inflating LLM context windows or confusing the model.

## Future Improvements
- Extending ingestion support to internal native Word documents (.docx) or image-based scans (OCR integration).
- Implementing visual administrative dashboards for university-wide, macro-level curriculum analytics.
- Fine-tuning a smaller, localized model specifically for academic validation to replace Mistral 7B, yielding faster inference times and lower resource utilization.

## Engineering Decisions
- **Used embedding-based retrieval before LLM to reduce hallucinations:** By injecting exact textbook/syllabus definitions into the LLM prompt (RAG methodology), we grounded the AI strictly in institutional data rather than the model's parametric memory.
- **Added similarity threshold to improve accuracy:** Employed a "Fast-Path Confidence Bound" (a deterministic cosine gatekeeper) which rejects low-relevance questions instantly. This bypasses the expensive LLM for a massive volume of queries, drastically reducing processing time and API/compute costs.
- **Designed modular backend for scalability:** Kept the Flask routing layer thin by partitioning core features (e.g. `bloom_classifier.py`, `co_mapper.py`) into independent, pure-function services. This allowed adding features backward-compatibly without risking the stability of the core ingestion loop.