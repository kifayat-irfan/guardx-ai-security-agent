"""Local embedding model — singleton, CPU-only, lazily loaded.

Model: sentence-transformers/all-MiniLM-L6-v2 (~90 MB download on first
run, cached in ~/.cache/huggingface afterwards; 384-dim vectors).
Resource use on this box: ~200-400 MB RAM while loaded, CPU inference.

The singleton is intentional: exactly one model instance per process.
Tests inject a stub embedder instead (no download, deterministic).
"""
from __future__ import annotations

import threading
from typing import Callable

_model = None
_model_name: str | None = None
_lock = threading.Lock()

EmbedFn = Callable[[list[str]], list[list[float]]]


def get_embedder(model_name: str) -> EmbedFn:
    """Return the process-wide embedding function for ``model_name``."""
    global _model, _model_name
    with _lock:
        if _model is None or _model_name != model_name:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(model_name, device="cpu")
            _model_name = model_name
        model = _model

    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    return embed


def embedding_dim(model_name: str) -> int:
    return len(get_embedder(model_name)(["probe"])[0])
