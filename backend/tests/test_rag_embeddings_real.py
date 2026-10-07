"""Real embedding-model smoke test (Phase 4).

Runs ONLY when GUARDX_REAL_EMBEDDINGS=1 — it downloads
sentence-transformers/all-MiniLM-L6-v2 (~90 MB) on first run and caches it
in ~/.cache/huggingface afterwards. Records real indexing/search timings
for docs/10-phase4-rag.md. Never runs in the default offline test suite.
"""
import os
import time
from pathlib import Path

import pytest

from app.rag.chunker import chunk_policies
from app.rag.embeddings import get_embedder
from app.rag.loader import load_policies
from app.rag.store import PolicyStore

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

pytestmark = pytest.mark.skipif(
    os.environ.get("GUARDX_REAL_EMBEDDINGS") != "1",
    reason="needs GUARDX_REAL_EMBEDDINGS=1 (downloads ~90MB model once)",
)


def test_real_model_index_and_search(tmp_path):
    t0 = time.perf_counter()
    embed = get_embedder(MODEL)
    load_ms = (time.perf_counter() - t0) * 1000

    docs = load_policies(POLICIES_DIR)
    chunks = chunk_policies(docs)

    t0 = time.perf_counter()
    vectors = embed([c.content for c in chunks])
    embed_ms = (time.perf_counter() - t0) * 1000

    assert len(vectors) == 20
    assert len(vectors[0]) == 384

    store = PolicyStore(tmp_path / "chroma", "real_model_test")
    store.upsert(chunks, vectors)
    assert store.count() == 20

    t0 = time.perf_counter()
    qv = embed(["A person entered the restricted server room without authorization"])[0]
    hits = store.query(qv, top_k=3)
    search_ms = (time.perf_counter() - t0) * 1000

    print(f"\nmodel load : {load_ms:.0f} ms")
    print(f"embed 20   : {embed_ms:.0f} ms ({embed_ms / 20:.1f} ms/chunk)")
    print(f"search     : {search_ms:.1f} ms")
    for h in hits:
        print(f"  {h['chunk_id']} dist={h['distance']:.3f}")

    top_ids = [h["chunk_id"] for h in hits]
    assert any(i.startswith("restricted-area#") for i in top_ids), (
        f"expected restricted-area chunks at top, got {top_ids}"
    )
