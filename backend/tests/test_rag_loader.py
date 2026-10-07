"""Policy loading/parsing tests (Phase 4)."""
from pathlib import Path

import pytest

from app.rag.loader import PolicyLoadError, load_policies, load_policy_file

POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"


def test_load_all_five_policies():
    docs = load_policies(POLICIES_DIR)
    assert len(docs) == 5
    ids = {d.policy_id for d in docs}
    assert ids == {
        "restricted-area", "after-hours-access", "visitor-authorization",
        "emergency-response", "incident-reporting",
    }


def test_policy_fields_and_sections():
    docs = {d.policy_id: d for d in load_policies(POLICIES_DIR)}
    doc = docs["restricted-area"]
    assert doc.title == "Restricted Area Policy"
    assert doc.version == "1.0"
    assert doc.effective_date == "2026-01-15"
    assert doc.category == "restricted_area"
    assert doc.source == "restricted-area-policy.md"
    headings = [h for h, _ in doc.sections]
    assert headings == [
        "Purpose", "Rules", "Severity Guidance", "Recommended Response",
    ]
    assert all(body for _, body in doc.sections)


def test_missing_front_matter_rejected(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("## Purpose\nNo front matter here.\n")
    with pytest.raises(PolicyLoadError):
        load_policy_file(p)


def test_missing_metadata_rejected(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("---\ntitle: No ID\n---\n## Purpose\nText.\n")
    with pytest.raises(PolicyLoadError):
        load_policy_file(p)


def test_no_sections_rejected(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text(
        "---\npolicy_id: x\ntitle: X\nversion: '1'\n"
        "effective_date: 2026-01-01\n---\nJust prose, no headings.\n"
    )
    with pytest.raises(PolicyLoadError):
        load_policy_file(p)


def test_missing_directory_rejected(tmp_path):
    with pytest.raises(PolicyLoadError):
        load_policies(tmp_path / "does-not-exist")


def test_empty_directory_loads_zero(tmp_path):
    assert load_policies(tmp_path) == []
