from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self):
        self.model = SentenceTransformer("intfloat/multilingual-e5-base")

    def embed(self, texts):
        # E5 models require prefixing:
        processed = [f"query: {t}" for t in texts]
        return self.model.encode(processed, normalize_embeddings=True).tolist()
