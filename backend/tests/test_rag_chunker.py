"""Chunking tests — deterministic IDs, metadata, splitting (Phase 4)."""
from pathlib import Path

from app.rag.chunker import chunk_policies, slugify
from app.rag.loader import load_policies

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def _docs():
    return load_policies(POLICIES_DIR)


def test_one_chunk_per_section():
    chunks = chunk_policies(_docs())
    # 5 policies x 4 sections each
    assert len(chunks) == 20


def test_chunk_ids_deterministic():
    first = [c.chunk_id for c in chunk_policies(_docs())]
    second = [c.chunk_id for c in chunk_policies(_docs())]
    assert first == second
    assert "restricted-area#purpose" in first
    assert "restricted-area#severity-guidance" in first


def test_chunk_metadata_complete():
    chunks = chunk_policies(_docs())
    chunk = next(c for c in chunks if c.chunk_id == "restricted-area#purpose")
    assert chunk.policy_id == "restricted-area"
    assert chunk.policy_title == "Restricted Area Policy"
    assert chunk.section == "Purpose"
    assert chunk.category == "restricted_area"
    assert chunk.version == "1.0"
    assert chunk.source == "restricted-area-policy.md"
    assert len(chunk.content) > 50


def test_long_section_splits_deterministically():
    docs = _docs()
    doc = next(d for d in docs if d.policy_id == "restricted-area")
    long_body = "\n\n".join(f"Paragraph {i} " * 40 for i in range(10))
    doc.sections = [("Rules", long_body)]
    chunks = chunk_policies([doc], max_chars=500)
    assert len(chunks) > 1
    ids = [c.chunk_id for c in chunks]
    assert ids == [c.chunk_id for c in chunk_policies([doc], max_chars=500)]
    assert all(i.startswith("restricted-area#rules-p") for i in ids)


def test_slugify():
    assert slugify("Severity Guidance") == "severity-guidance"
    assert slugify("  ## Weird__Title!! ") == "weird-title"
