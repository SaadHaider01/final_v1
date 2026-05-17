import os
import re
import chromadb
from typing import List
import spacy

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

def extract_concepts(text: str) -> List[str]:
    """Extract technical noun phrases, capitalized entities, and acronyms."""
    nlp = get_nlp()
    # Limit text length to avoid spacy memory issues on massive documents
    doc = nlp(text[:100000])
    concepts = set()
    
    # 1. Noun chunks (removing determiners)
    for chunk in doc.noun_chunks:
        tokens = [t for t in chunk if t.pos_ not in ("DET", "PRON", "PUNCT")]
        if not tokens:
            continue
        phrase = " ".join([t.text for t in tokens]).strip().lower()
        if 3 < len(phrase) < 40:
            concepts.add(phrase)
            
    # 2. Capitalized phrases (e.g., Hash Function, RSA)
    caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    for c in caps:
        if len(c) > 3:
            concepts.add(c.lower())
            
    # 3. Acronyms
    acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
    for a in acronyms:
        concepts.add(a.lower())
        
    return list(concepts)

class ConceptStore:
    """
    Builds a subject-local concept index and provides semantic boosting
    for conceptual question analysis.
    """
    def __init__(self, embed_fn, persist_dir: str = "./data/vector_db"):
        self.embed_fn = embed_fn
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="concept_store",
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_syllabus_concepts(self, syllabus_id: str, chunks: List[str]):
        """Extract and store concepts from chunks during ingestion."""
        if not chunks:
            return
            
        full_text = " ".join(chunks)
        concepts = extract_concepts(full_text)
        if not concepts:
            return
            
        # Prevent duplicates
        concepts = list(set(concepts))
        
        embeddings = self.embed_fn(concepts, task="passage")
        ids = [f"{syllabus_id}_c_{i}" for i in range(len(concepts))]
        metas = [{"syllabus_id": syllabus_id, "concept": c} for c in concepts]
        
        batch_size = 500
        for i in range(0, len(concepts), batch_size):
            self.collection.add(
                ids=ids[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                metadatas=metas[i:i+batch_size],
                documents=concepts[i:i+batch_size]
            )

    def compute_concept_boost(self, question: str, syllabus_id: str) -> float:
        """
        Compare question concepts semantically against LOCAL syllabus concepts ONLY.
        Returns a retrieval boost if local curriculum concept alignment exists.
        """
        if not syllabus_id:
            return 0.0
            
        q_concepts = extract_concepts(question)
        if not q_concepts:
            return 0.0
            
        q_embeddings = self.embed_fn(q_concepts, task="query")
        
        try:
            results = self.collection.query(
                query_embeddings=q_embeddings,
                n_results=1,
                where={"syllabus_id": syllabus_id}
            )
        except Exception:
            return 0.0
            
        distances = results.get("distances", [])
        if not distances:
            return 0.0
            
        best_sim = 0.0
        for dist_list in distances:
            if dist_list:
                sim = max(0.0, min(1.0, 1.0 - float(dist_list[0])))
                if sim > best_sim:
                    best_sim = sim
                    
        # Safe Hybrid Boosting: Boost ONLY when local curriculum concept alignment exists.
        # This will lift conceptual paraphrases (e.g. "reduce redundancy" -> "normalization")
        # without hardcoding mappings.
        if best_sim >= 0.85:
            return 0.12  # Strong conceptual overlap
        elif best_sim >= 0.75:
            return 0.06  # Moderate conceptual overlap
        return 0.0
