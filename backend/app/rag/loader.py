"""Policy document loading and parsing.

Policies are Markdown files with YAML front-matter::

    ---
    policy_id: restricted-area
    title: Restricted Area Policy
    version: "1.0"
    effective_date: 2026-01-15
    category: restricted_area
    ---
    ## Purpose
    ...

Required front-matter keys: policy_id, title, version, effective_date.
Sections are the ``##`` headings; body text under each heading is the
section content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED_META = ("policy_id", "title", "version", "effective_date")

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class PolicyDocument:
    policy_id: str
    title: str
    version: str
    effective_date: str
    category: str
    source: str  # filename
    sections: list[tuple[str, str]] = field(default_factory=list)
    # sections: [(heading, body_text), ...] in document order


class PolicyLoadError(ValueError):
    pass


def load_policy_file(path: Path) -> PolicyDocument:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise PolicyLoadError(f"{path.name}: missing YAML front-matter")
    try:
        _, front, body = text.split("---", 2)
    except ValueError:
        raise PolicyLoadError(f"{path.name}: malformed front-matter block")
    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError as exc:
        raise PolicyLoadError(f"{path.name}: invalid YAML: {exc}")
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise PolicyLoadError(f"{path.name}: missing metadata {missing}")

    sections: list[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        heading = m.group(1).strip()
        content = body[start:end].strip()
        if heading and content:
            sections.append((heading, content))
    if not sections:
        raise PolicyLoadError(f"{path.name}: no '##' sections found")

    return PolicyDocument(
        policy_id=str(meta["policy_id"]),
        title=str(meta["title"]),
        version=str(meta["version"]),
        effective_date=str(meta["effective_date"]),
        category=str(meta.get("category", "")),
        source=path.name,
        sections=sections,
    )


def load_policies(directory: Path | str) -> list[PolicyDocument]:
    """Load every ``*.md`` policy in the directory (sorted, deterministic).

    ``README.md`` is corpus documentation, not a policy, and is skipped.
    Any other malformed file raises PolicyLoadError.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise PolicyLoadError(f"policies directory not found: {directory}")
    docs = []
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        docs.append(load_policy_file(path))
    return docs
