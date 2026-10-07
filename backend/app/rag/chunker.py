"""Deterministic policy chunking — one chunk per policy section.

Chunk IDs are ``<policy_id>#<section-slug>``: stable across reindexes, so
upserts never duplicate and citations stay valid. Section bodies longer than
``max_chars`` are split on paragraph boundaries with the same deterministic
scheme (``<policy_id>#<section-slug>-p<n>``).
"""
from __future__ import annotations

import re

from app.rag.loader import PolicyDocument
from app.rag.schemas import PolicyChunk


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def chunk_policy(doc: PolicyDocument, max_chars: int = 2000) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for heading, body in doc.sections:
        slug = slugify(heading)
        if len(body) <= max_chars:
            parts = [(slug, body)]
        else:
            parts = [
                (f"{slug}-p{n}", para)
                for n, para in enumerate(_split_paragraphs(body, max_chars))
            ]
        for part_slug, content in parts:
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{doc.policy_id}#{part_slug}",
                    policy_id=doc.policy_id,
                    policy_title=doc.title,
                    section=heading,
                    category=doc.category,
                    version=doc.version,
                    source=doc.source,
                    content=content.strip(),
                )
            )
    return chunks


def _split_paragraphs(body: str, max_chars: int) -> list[str]:
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    out, buf = [], ""
    for para in paras:
        if buf and len(buf) + len(para) + 2 > max_chars:
            out.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        out.append(buf)
    return out or [body]


def chunk_policies(
    docs: list[PolicyDocument], max_chars: int = 2000
) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for doc in docs:
        chunks.extend(chunk_policy(doc, max_chars=max_chars))
    return chunks
