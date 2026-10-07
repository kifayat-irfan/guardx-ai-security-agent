"""ChromaDB vector store — persistent local index (derived, rebuildable).

PostgreSQL remains the source of truth; this collection is a derived index
that can be dropped and rebuilt from ``policies/`` at any time via reindex.
"""
from __future__ import annotations

import threading
from pathlib import Path

import chromadb

from app.rag.schemas import PolicyChunk


class PolicyStore:
    """Thin wrapper over a persistent ChromaDB collection."""

    def __init__(self, persist_dir: Path | str, collection: str):
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )
        self._lock = threading.Lock()

    @property
    def collection_name(self) -> str:
        return self._collection.name

    def count(self) -> int:
        with self._lock:
            return self._collection.count()

    def upsert(self, chunks: list[PolicyChunk],
               embeddings: list[list[float]]) -> None:
        """Insert or update chunks by deterministic chunk_id — no duplicates."""
        if not chunks:
            return
        with self._lock:
            self._collection.upsert(
                ids=[c.chunk_id for c in chunks],
                embeddings=embeddings,
                documents=[c.content for c in chunks],
                metadatas=[
                    {
                        "policy_id": c.policy_id,
                        "policy_title": c.policy_title,
                        "section": c.section,
                        "category": c.category,
                        "version": c.version,
                        "source": c.source,
                        "chunk_id": c.chunk_id,
                    }
                    for c in chunks
                ],
            )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        where: dict | None = None,
    ) -> list[dict]:
        """Return top-k hits as dicts with chunk fields + distance."""
        with self._lock:
            res = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        hits = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            hits.append(
                {
                    "chunk_id": meta["chunk_id"],
                    "policy_id": meta["policy_id"],
                    "policy_title": meta["policy_title"],
                    "section": meta["section"],
                    "content": doc,
                    "distance": float(dist),
                    "metadata": dict(meta),
                }
            )
        return hits

    def get_chunk_ids(self) -> set[str]:
        with self._lock:
            res = self._collection.get(include=[])
        return set(res["ids"])

    def reset(self) -> None:
        """Drop all vectors (tests / full rebuild)."""
        with self._lock:
            self._client.delete_collection(self._collection.name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection.name, metadata={"hnsw:space": "cosine"}
            )
