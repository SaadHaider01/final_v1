from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self):
        # Using 'cuda' to leverage the NVIDIA GTX 1650 for 5-10x faster embeddings
        self.model = SentenceTransformer("intfloat/multilingual-e5-base", device='cuda')

    def embed(self, texts, task="query"):
        # E5 models require prefixing: 'query: ' for queries, 'passage: ' for documents
        prefix = "query: " if task == "query" else "passage: "
        processed = [f"{prefix}{t}" for t in texts]
        return self.model.encode(processed, normalize_embeddings=True).tolist()
