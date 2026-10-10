import os
import logging
import math
import re
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingEngine:
    """Vector embedding engine supporting Google GenAI and local semantic fallback."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self.model = model or os.environ.get("DEFAULT_EMBEDDING_MODEL", "gemini-embedding-001")
        self._genai_client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Google GenAI embedding client with model {self.model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI client: {e}. Falling back to local embeddings.")
                self._genai_client = None
        else:
            logger.info("No Gemini API key provided. Using deterministic local semantic embedding engine.")

    def embed_text(self, text: str) -> np.ndarray:
        """Compute normalized embedding vector for a single text."""
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            cleaned_text = "empty"

        if self._genai_client:
            try:
                response = self._genai_client.models.embed_content(
                    model=self.model,
                    contents=cleaned_text
                )
                if response.embeddings and len(response.embeddings) > 0:
                    vec = np.array(response.embeddings[0].values, dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    return vec / norm if norm > 0 else vec
            except Exception as e:
                logger.warning(f"Google GenAI embedding failed ({e}); falling back to local semantic embedding.")

        return self._local_embed(cleaned_text)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Compute normalized embedding vectors for multiple texts."""
        return [self.embed_text(t) for t in texts]

    def _local_embed(self, text: str, dim: int = 384) -> np.ndarray:
        """Lightweight deterministic semantic hash + character n-gram local embedding."""
        vec = np.zeros(dim, dtype=np.float32)
        tokens = re.findall(r'\b\w+\b', text.lower())

        if not tokens:
            return vec

        for i, token in enumerate(tokens):
            # Unigram hash
            h = hash(token) % dim
            vec[h] += 1.0 / math.sqrt(i + 1)

            # Character 3-grams for subword semantic matching
            if len(token) >= 3:
                for j in range(len(token) - 2):
                    sub = token[j:j+3]
                    sub_h = hash(sub) % dim
                    vec[sub_h] += 0.4 / math.sqrt(i + 1)

            # Bigram with next token
            if i < len(tokens) - 1:
                bigram = f"{token}_{tokens[i+1]}"
                bi_h = hash(bigram) % dim
                vec[bi_h] += 1.2 / math.sqrt(i + 1)

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    @staticmethod
    def compute_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        if vec_a is None or vec_b is None:
            return 0.0
        # If dimensions differ, slice to matching min dimension
        if vec_a.shape != vec_b.shape:
            min_dim = min(len(vec_a), len(vec_b))
            vec_a = vec_a[:min_dim]
            vec_b = vec_b[:min_dim]

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        return max(-1.0, min(1.0, similarity))
