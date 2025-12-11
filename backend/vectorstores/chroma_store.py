import chromadb

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
