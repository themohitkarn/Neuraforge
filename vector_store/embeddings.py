from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingsModel:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def get_embedding(self, text: str) -> np.ndarray:
        """
        Embeds a single string and returns a 1D numpy array.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    def get_embeddings(self, texts: list[str]) -> np.ndarray:
        """
        Embeds a list of strings and returns a 2D numpy array.
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings
