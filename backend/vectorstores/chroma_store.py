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

    def add_syllabus(self, syllabus_id, chunks):
        embeddings = self.embed_fn(chunks)

        ids = [f"{syllabus_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"syllabus_id": syllabus_id, "chunk": chunk} for chunk in chunks]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=chunks  # store visible text
        )

    def query(self, query_text, k=3):
        query_embedding = self.embed_fn([query_text])

        result = self.collection.query(
            query_embeddings=query_embedding,
            n_results=k
        )
        return result
