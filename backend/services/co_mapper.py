"""
services/co_mapper.py
----------------------
Feature 3: Course Outcome (CO) mapping.
Feature 3B: Program Outcome (PCO/PO) mapping.

COs are stored in a dedicated ChromaDB collection (semantic search).
PCOs are stored as a simple in-memory dict (CO→PO lookup — no embedding needed).

Usage (ingestion):
    co_mapper.add_cos(syllabus_id, [
        {"co_id": "CO1", "text": "Understand principles of networking"},
        {"co_id": "CO2", "text": "Apply cryptographic techniques"},
    ])
    co_mapper.add_pcos(syllabus_id, [
        {"co_id": "CO1", "pco_id": "PO1"},
        {"co_id": "CO2", "pco_id": "PO2"},
    ])

Usage (analysis):
    co  = co_mapper.map_question_to_co(question, syllabus_id)  # → "CO2" or None
    pco = co_mapper.get_pco_for_co(syllabus_id, co)           # → "PO2" or None
"""

import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import chromadb


class CoMapper:
    """
    Manages CO semantic search (ChromaDB) and PCO direct lookup (dict).
    Reuses the same embed_fn as the main VectorStore — no extra models.
    """

    COLLECTION_NAME = "course_outcomes"

    def __init__(self, embed_fn, persist_dir: str = "./data/vector_db"):
        self.embed_fn  = embed_fn
        self.client    = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # PCO lookup: {syllabus_id: {"CO1": "PO2", "CO2": "PO1"}}
        self._co_to_pco: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # CO Ingestion (existing — unchanged)
    # ------------------------------------------------------------------

    def add_cos(self, syllabus_id: str, cos: list) -> int:
        """
        Store a list of COs for a given syllabus (semantic embeddings).

        Args:
            syllabus_id: matches the ID created during /ingest_syllabus
            cos: list of dicts: [{"co_id": "CO1", "text": "..."}, ...]

        Returns:
            Number of CO entries stored.
        """
        if not cos:
            return 0

        texts      = [c["text"] for c in cos]
        embeddings = self.embed_fn(texts)

        ids       = [f"{syllabus_id}_co_{c['co_id']}" for c in cos]
        metadatas = [
            {"syllabus_id": syllabus_id, "co_id": c["co_id"]}
            for c in cos
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts,
        )
        return len(cos)

    # ------------------------------------------------------------------
    # PCO Ingestion (NEW — Feature 3B)
    # ------------------------------------------------------------------

    def add_pcos(self, syllabus_id: str, pcos: list) -> int:
        """
        Store CO→PCO mapping for a given syllabus.

        Args:
            syllabus_id: syllabus this mapping belongs to
            pcos: list of dicts: [{"co_id": "CO1", "pco_id": "PO2"}, ...]

        Returns:
            Number of PCO mappings stored.
        """
        if not pcos:
            return 0
        mapping = {p["co_id"].upper(): p["pco_id"].upper() for p in pcos if "co_id" in p and "pco_id" in p}
        self._co_to_pco.setdefault(syllabus_id, {}).update(mapping)
        return len(mapping)

    def get_pco_for_co(self, syllabus_id: str, co_id: str) -> str | None:
        """
        Look up the Program Outcome for a given CO.

        Args:
            syllabus_id: the syllabus the CO belongs to
            co_id:       e.g. "CO2"

        Returns:
            pco_id string e.g. "PO1", or None if no mapping stored.
        """
        if not syllabus_id or not co_id:
            return None
        syllabus_map = self._co_to_pco.get(syllabus_id, {})
        return syllabus_map.get(co_id.upper(), None)

    # ------------------------------------------------------------------
    # CO Query (existing — unchanged)
    # ------------------------------------------------------------------

    def map_question_to_co(
        self,
        question: str,
        syllabus_id: str = None,
    ) -> str | None:
        """
        Embed the question and return the best-matching CO id (e.g. "CO2").

        Args:
            question:    Raw question text.
            syllabus_id: If provided, restrict search to this syllabus's COs.

        Returns:
            co_id string or None.
        """
        if self.collection.count() == 0:
            return None

        q_embedding = self.embed_fn([question])
        where       = {"syllabus_id": syllabus_id} if syllabus_id else None

        try:
            kwargs = dict(query_embeddings=q_embedding, n_results=1)
            if where:
                kwargs["where"] = where
            result = self.collection.query(**kwargs)
        except Exception:
            return None

        metadatas = result.get("metadatas") or [[]]
        if not metadatas or not metadatas[0]:
            return None

        return metadatas[0][0].get("co_id", None)
