import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import chromadb

# ============================================
# Function to fully disable telemetry at runtime
# ============================================
def disable_chroma_telemetry():
    """Patch all telemetry modules AFTER Chroma loads them."""
    try:
        # Patch product telemetry (your actual error)
        prod = __import__("chromadb.telemetry.product", fromlist=["capture"])
        prod.capture = lambda *args, **kwargs: None
    except Exception:
        pass

    try:
        events = __import__("chromadb.telemetry.events", fromlist=["capture"])
        events.capture = lambda *args, **kwargs: None
    except Exception:
        pass

    try:
        posthog = __import__("chromadb.telemetry.posthog", fromlist=["Posthog"])
        class DummyPosthog:
            def capture(self, *a, **kw): return None
            def shutdown(self): return None
        posthog.Posthog = DummyPosthog
    except Exception:
        pass

    try:
        ot = __import__("chromadb.telemetry.opentelemetry", fromlist=["configure_otel"])
        ot.configure_otel = lambda *a, **kw: None
    except Exception:
        pass

# Call it once immediately
disable_chroma_telemetry()





class VectorStore:
    def __init__(self, embed_fn, persist_dir="./data/vector_db"):
        self.embed_fn = embed_fn  # we fully control embedding generation
        self.client = chromadb.PersistentClient(path=persist_dir)

        # Create or get a collection WITHOUT Chroma auto-embedding
        self.collection = self.client.get_or_create_collection(
            name="syllabi",
            metadata={"hnsw:space": "cosine"}  # ensure cosine scoring
        )

    def add_syllabus(self, syllabus_id, chunks, extra_meta=None):
        """
        chunks: list of str  OR  list of (text, module_label) tuples.
        Module labels are stored in ChromaDB metadata for later retrieval.
        extra_meta: dict of additional metadata (e.g. department, subject_name) to store with every chunk.
        """
        # Normalise to (text, label) pairs
        pairs = []
        for c in chunks:
            if isinstance(c, tuple):
                pairs.append(c)
            else:
                pairs.append((c, None))

        texts      = [p[0] for p in pairs]
        embeddings = self.embed_fn(texts, task="passage")

        ids       = [f"{syllabus_id}_{i}" for i in range(len(texts))]
        metadatas = []
        for t, m in pairs:
            meta = {"syllabus_id": syllabus_id, "chunk": t, "module": m or ""}
            if extra_meta:
                meta.update(extra_meta)
            metadatas.append(meta)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )

    def exists(self, syllabus_id: str) -> bool:
        """
        Return True if any chunks with this syllabus_id are already stored.
        Used to prevent duplicate embeddings during selective ingestion.
        """
        try:
            result = self.collection.get(
                where={"syllabus_id": syllabus_id},
                limit=1,
            )
            return bool(result and result.get("ids"))
        except Exception:
            return False

    def delete_syllabus(self, syllabus_id):
        """Remove all chunks belonging to a given syllabus_id from the collection."""
        try:
            self.collection.delete(where={"syllabus_id": syllabus_id})
            return True
        except Exception as e:
            print(f"Error deleting syllabus {syllabus_id}: {e}")
            return False

    def reset_collection(self):
        """
        Wipe ALL vectors from the collection.
        Safer than deleting per-syllabus when data is badly polluted.
        """
        try:
            all_data = self.collection.get()
            if all_data and all_data.get("ids"):
                self.collection.delete(ids=all_data["ids"])
                print(f"[Vector DB] Reset: removed {len(all_data['ids'])} vectors.")
            return True
        except Exception as e:
            print(f"[Vector DB] Reset error: {e}")
            return False

    def query(self, query_text, k=3, syllabus_id=None, metadata_filter=None):
        query_embedding = self.embed_fn([query_text], task="query")

        where_clause = None
        if syllabus_id:
            where_clause = {"syllabus_id": syllabus_id}
            print(f"[Vector Retrieval] syllabus_id={syllabus_id} | k={k}")
        elif metadata_filter:
            where_clause = metadata_filter

        try:
            result = self.collection.query(
                query_embeddings=query_embedding,
                n_results=k,
                where=where_clause
            )
        except Exception as e:
            err = str(e)
            # ChromaDB Rust HNSW "Nothing found on disk" — happens when the index
            # hasn't been flushed to disk yet (e.g. fresh collection on first query).
            if "Nothing found on disk" in err or "hnsw segment" in err.lower():
                print(f"[Vector Retrieval] WARNING: HNSW index not ready yet ({err[:80]}). Returning empty.")
                return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
            raise

        # Log filtered chunk count
        docs = result.get("documents") or [[]]
        print(f"[Vector Retrieval] filtered_chunks={len(docs[0]) if docs else 0}")
        return result

