"""
services/co_mapper.py
----------------------
Feature 3: Course Outcome (CO) mapping.
Feature 3B: Program Outcome (PCO/PO) mapping.

COs are stored in a dedicated ChromaDB collection (semantic search).
PCOs are stored as a simple in-memory dict (CO->PO lookup - no embedding needed).

Metadata schema per stored CO:
    course_code  : "PEC-IT801B"
    full_co_id   : "PEC-IT801B.CO2"
    display_co   : "CO2"
    syllabus_id  : "IT-VIII-PEC-IT801B"

Usage (ingestion):
    co_mapper.add_cos(syllabus_id, [
        {"co_id": "CO1", "full_co_id": "PEC-IT801B.CO1", "course_code": "PEC-IT801B",
         "text": "PEC-IT801B.CO1 Understand principles of networking Apply"},
        ...
    ])

Usage (analysis):
    co  = co_mapper.map_question_to_co(question, syllabus_id)  # -> "CO2" or None
    pco = co_mapper.get_pco_for_co(syllabus_id, co)           # -> "PO2" or None
"""

import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import chromadb
from debug_logger import dsection, dlog, dlist, derror, ddivider


class CoMapper:
    """
    Manages CO semantic search (ChromaDB) and PCO direct lookup (dict).
    Reuses the same embed_fn as the main VectorStore -- no extra models.
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
    # CO Ingestion
    # ------------------------------------------------------------------

    def add_cos(self, syllabus_id: str, cos: list) -> int:
        """
        Store a list of COs for a given syllabus (semantic embeddings).

        Args:
            syllabus_id : matches the ID created during /ingest_syllabus
            cos         : list of dicts with keys:
                            co_id       - display id e.g. "CO2"
                            full_co_id  - e.g. "PEC-IT801B.CO2"  (optional)
                            course_code - e.g. "PEC-IT801B"       (optional)
                            text        - the outcome text

        Returns:
            Number of CO entries actually stored (skipping duplicates).
        """
        if not cos:
            return 0

        stored = 0
        texts_to_add = []
        ids_to_add   = []
        metas_to_add = []

        for c in cos:
            display_co  = c.get("co_id", "")
            course_code = c.get("course_code", "") or syllabus_id
            full_co_id  = c.get("full_co_id", "") or f"{course_code}.{display_co}"
            text        = c.get("text", "")

            # Stable, unique ChromaDB document id keyed on (course_code, full_co_id)
            doc_id = f"{course_code}::{full_co_id}"

            # Duplicate check by (course_code, full_co_id)
            try:
                existing = self.collection.get(ids=[doc_id])
                if existing and existing.get("ids"):
                    print(f"  [CO Mapper] Duplicate detected  {full_co_id} -- skipping")
                    continue
            except Exception:
                pass  # not found -> safe to insert

            texts_to_add.append(text)
            ids_to_add.append(doc_id)
            metas_to_add.append({
                "syllabus_id": syllabus_id,
                "course_code": course_code,
                "full_co_id" : full_co_id,
                "display_co" : display_co,
                # legacy key kept for backward compat
                "co_id"      : display_co,
            })
            print(f"  [CO Mapper] Registered CO  {full_co_id}")
            stored += 1

        if texts_to_add:
            embeddings = self.embed_fn(texts_to_add, task="passage")
            self.collection.add(
                ids        = ids_to_add,
                embeddings = embeddings,
                metadatas  = metas_to_add,
                documents  = texts_to_add,
            )

        return stored

    def clear_cos_for_syllabus(self, syllabus_id: str) -> int:
        """
        Delete all CO records stored for this syllabus_id (any ID format).
        Call this before re-ingesting to prevent duplicate accumulation.

        Returns:
            Number of records deleted.
        """
        try:
            existing = self.collection.get(where={"syllabus_id": syllabus_id})
            ids_to_delete = existing.get("ids") or []
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                print(f"  [CO Mapper] Cleared {len(ids_to_delete)} stale CO records for {syllabus_id}")
                return len(ids_to_delete)
        except Exception as e:
            print(f"  [CO Mapper] Clear failed for {syllabus_id}: {e}")
        return 0

    # ------------------------------------------------------------------
    # PCO Ingestion (Feature 3B)
    # ------------------------------------------------------------------

    def add_pcos(self, syllabus_id: str, pcos: list) -> int:
        """
        Store CO->PCO mapping for a given syllabus.

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
    # CO Query
    # ------------------------------------------------------------------

    def map_question_to_co(
        self,
        question: str,
        syllabus_id: str = None,
    ) -> str | None:
        """
        Embed the question and return the best-matching CO display_id (e.g. "CO2").
        """
        # Section 8 - CO Mapper debug
        dsection("CO Mapper")
        dlog("CO Mapper", "Question",    question[:100])
        dlog("CO Mapper", "Syllabus ID", syllabus_id or "(global)")

        if self.collection.count() == 0:
            derror("CO Mapper", "CO collection is empty", "No COs have been ingested yet")
            return None

        q_embedding = self.embed_fn([question], task="query")
        where       = {"syllabus_id": syllabus_id} if syllabus_id else None

        try:
            n_results = min(10, self.collection.count())
            kwargs = dict(query_embeddings=q_embedding, n_results=n_results,
                          include=["metadatas", "distances", "documents"])
            if where:
                kwargs["where"] = where
            result = self.collection.query(**kwargs)
        except Exception as e:
            derror("CO Mapper", "Query failed", str(e))
            return None

        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        documents = result.get("documents") or [[]]

        if not metadatas or not metadatas[0]:
            derror("CO Mapper", "No CO results returned", "Check if syllabus_id filter is too strict")
            return None

        # Print ranked CO similarities using display_co + full_co_id
        dlog("CO Mapper", "CO Similarities", "(cosine, descending)")
        for meta, dist, doc in zip(metadatas[0], distances[0], documents[0]):
            display_co = meta.get("display_co") or meta.get("co_id", "?")
            full_co_id = meta.get("full_co_id", display_co)
            sim        = max(0.0, 1.0 - dist / 2.0)
            snippet    = str(doc)[:60].replace("\n", " ")
            dlog("CO Mapper", f"  {display_co}", f"{sim:.4f}  ({full_co_id})  -- {snippet}")

        selected_meta    = metadatas[0][0]
        selected_display = selected_meta.get("display_co") or selected_meta.get("co_id", None)
        selected_full    = selected_meta.get("full_co_id", selected_display)
        best_sim         = max(0.0, 1.0 - distances[0][0] / 2.0)

        dlog("CO Mapper", "Matched",     selected_full or "None")
        dlog("CO Mapper", "Similarity",  f"{best_sim:.4f}")
        dlog("CO Mapper", "Selected CO", selected_display or "None")
        if selected_display:
            dlog("CO Mapper", "Reason",
                 f"Highest cosine similarity among all COs for {syllabus_id or 'global'}")
        else:
            derror("CO Mapper", "No CO selected",
                   "metadatas[0][0] had no display_co or co_id field")

        return selected_display

    def map_question_to_co_full(
        self,
        question: str,
        syllabus_id: str = None,
    ) -> dict | None:
        """
        Like map_question_to_co but returns a dict with display_co and full_co_id.
        Used by callers that want to surface the full identifier in the API response.
        """
        if self.collection.count() == 0:
            return None

        q_embedding = self.embed_fn([question], task="query")
        where       = {"syllabus_id": syllabus_id} if syllabus_id else None

        try:
            kwargs = dict(query_embeddings=q_embedding, n_results=1,
                          include=["metadatas", "distances"])
            if where:
                kwargs["where"] = where
            result = self.collection.query(**kwargs)
        except Exception:
            return None

        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        if not metadatas or not metadatas[0]:
            return None

        meta = metadatas[0][0]
        dist = distances[0][0]
        sim  = max(0.0, 1.0 - dist / 2.0)

        return {
            "display_co" : meta.get("display_co") or meta.get("co_id"),
            "full_co_id" : meta.get("full_co_id"),
            "course_code": meta.get("course_code"),
            "similarity" : sim,
        }
