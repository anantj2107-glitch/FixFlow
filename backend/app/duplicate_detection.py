"""Private, ranked possible-duplicate suggestions for unresolved tickets."""

from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from backend.app.text_normalization import normalize_ticket_text


@dataclass(frozen=True)
class Candidate:
    id: str
    category: str
    block: str
    room: str
    description: str
    status: str


class DuplicateDetector:
    """Embedding-first detector with transparent lexical fallback.

    `sentence-transformers` is optional. Import/load happens only on first
    request and failures permanently select fallback mode for this process.
    """

    def __init__(self, threshold: float | None = None, embeddings_enabled: bool | None = None):
        self.threshold = threshold if threshold is not None else float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.62"))
        self.embeddings_enabled = embeddings_enabled if embeddings_enabled is not None else os.getenv("DUPLICATE_EMBEDDINGS_ENABLED", "true").casefold() == "true"
        self._model = None
        self._model_attempted = False
        self._model_error: str | None = None
        self._embedding_cache: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @property
    def method(self) -> str:
        return "embedding" if self._model is not None else "lexical_fallback"

    def _load_model(self):
        if not self.embeddings_enabled or self._model_attempted:
            return self._model
        with self._lock:
            if self._model_attempted:
                return self._model
            self._model_attempted = True
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as error:  # dependency, download, model, runtime failures
                self._model_error = type(error).__name__
                self._model = None
        return self._model

    @staticmethod
    def _lexical_similarity(left: str, right: str) -> float:
        left_tokens, right_tokens = set(left.split()), set(right.split())
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        sequence = SequenceMatcher(None, left, right).ratio()
        return round((0.7 * overlap) + (0.3 * sequence), 4)

    def _embedding(self, normalized_text: str) -> list[float] | None:
        if not normalized_text:
            return None
        model = self._load_model()
        if model is None:
            return None
        with self._lock:
            cached = self._embedding_cache.get(normalized_text)
        if cached is not None:
            return cached
        try:
            encoded = model.encode(normalized_text, normalize_embeddings=True)
            embedding = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
            with self._lock:
                self._embedding_cache[normalized_text] = embedding
            return embedding
        except Exception as error:
            self._model_error = type(error).__name__
            return None

    def embedding_for(self, value: object) -> list[float] | None:
        """Expose cached optional embeddings for other local recommendation work."""
        return self._embedding(normalize_ticket_text(value))

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_size = math.sqrt(sum(value * value for value in left))
        right_size = math.sqrt(sum(value * value for value in right))
        return numerator / (left_size * right_size) if left_size and right_size else 0.0

    def suggest(self, source: Candidate, candidates: Iterable[Candidate], *, exclude_id: str | None = None) -> tuple[list[dict], str]:
        source_text = normalize_ticket_text(source.description)
        if not source_text:
            return [], "lexical_fallback"
        source_embedding = self._embedding(source_text)
        method = "embedding" if source_embedding is not None else "lexical_fallback"
        suggestions = []
        for candidate in candidates:
            if candidate.id == exclude_id or candidate.status == "Resolved" or candidate.category != source.category:
                continue
            candidate_text = normalize_ticket_text(candidate.description)
            if not candidate_text:
                continue
            candidate_embedding = self._embedding(candidate_text) if source_embedding is not None else None
            content_score = self._cosine(source_embedding, candidate_embedding) if candidate_embedding is not None else self._lexical_similarity(source_text, candidate_text)
            score = (content_score * 0.82) + (0.12 if candidate.block == source.block else 0.0) + (0.06 if normalize_ticket_text(candidate.room) == normalize_ticket_text(source.room) else 0.0)
            if score < self.threshold:
                continue
            reasons = ["same category"]
            if candidate.block == source.block:
                reasons.append("same block")
            reasons.append("semantic description similarity" if method == "embedding" else "lexical fallback similarity")
            suggestions.append({"ticket_id": candidate.id, "similarity": round(min(score, 1.0), 3), "method": method, "reason": "; ".join(reasons)})
        return sorted(suggestions, key=lambda item: item["similarity"], reverse=True)[:3], method
