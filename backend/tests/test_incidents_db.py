"""Phase 7: incident persistence + reporting tests (dedicated Postgres DB).

Uses the `guardx_test` database — never touches the dev `guardx` database.
Tables are truncated after every test.
"""
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.incidents.repository import IncidentRepository
from app.incidents.service import get_incident_service
from app.main import app
from app.models.incident import Incident
from app.models.incident_report import IncidentReport
from tests.test_incidents_workflow import (
    POLICIES_DIR,
    make_event,
    make_service,
)

TEST_DB_URL = get_settings().database_url.rsplit("/", 1)[0] + "/guardx_test"


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM incident_reports"))
        conn.execute(text("DELETE FROM incidents"))


@pytest.fixture()
def api_client(pg_engine, tmp_path):
    Session = sessionmaker(bind=pg_engine)
    policies = tmp_path / "policies"
    shutil.copytree(POLICIES_DIR, policies)
    svc, _ = make_service(tmp_path, collection="test_inc7_api",
                          policies_dir=policies)

    def _override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_incident_service] = lambda: svc
    with TestClient(app) as c:
        yield c, svc, policies
    app.dependency_overrides.clear()
    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM incident_reports"))
        conn.execute(text("DELETE FROM incidents"))


def _decision(status="completed", severity="HIGH"):
    return {
        "workflow_id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "status": status,
        "summary": "A person entered the restricted server room.",
        "severity": severity,
        "recommended_action": "Notify security.",
        "confidence": 0.91,
        "cited_policy_chunk_ids": ["restricted-area#rules"],
        "retrieved_policy_count": 3,
        "error": None,
        "started_at": "2026-10-07T00:00:00+00:00",
        "finished_at": "2026-10-07T00:00:01+00:00",
        "duration_ms": 15.0,
    }


def _analysis():
    return {
        "summary": "A person entered the restricted server room.",
        "severity": "HIGH",
        "recommended_action": "Notify security.",
        "cited_policy_chunk_ids": ["restricted-area#rules"],
        "reasoning": "Fact: zone_enter. Policy: HIGH.",
        "confidence": 0.91,
    }


# -- 1-2. models ---------------------------------------------------------------


def test_incident_model_roundtrip(db):
    repo = IncidentRepository(db)
    ev = make_event().model_dump(mode="json")
    incident = repo.create_incident(ev, _decision())
    assert incident.id is not None
    assert incident.zone_name == "server-room"
    assert incident.status == "completed"
    assert incident.event_data["tracking_id"] == 2
    assert incident.bounding_box == [0.4, 0.5, 0.6, 0.9]


def test_report_model_and_relationship(db):
    repo = IncidentRepository(db)
    ev = make_event().model_dump(mode="json")
    incident, report = repo.persist_workflow_result(
        ev, _decision(), _analysis(), ["restricted-area#rules"]
    )
    assert report is not None
    assert report.incident_id == incident.id
    assert report.cited_policy_chunk_ids == ["restricted-area#rules"]
    assert report.retrieved_chunk_ids == ["restricted-area#rules"]
    # relationship
    assert incident.report.id == report.id
    fetched = repo.get_report(incident.id)
    assert fetched.id == report.id


# -- 3-5. migration ---------------------------------------------------------------


def _incident_tables(pg_engine):
    with pg_engine.begin() as conn:
        return sorted(r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename IN ('incidents','incident_reports')"
        )).fetchall())


def _alembic(*args):
    """Run the real alembic CLI against the TEST database only."""
    import os
    import subprocess
    import sys

    backend = Path(__file__).resolve().parent.parent
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=backend, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc


def test_migration_upgrade_downgrade_reupgrade(pg_engine):
    from app.core.database import Base
    import app.models  # noqa: F401  (register models)

    # start from a known-good migrated state
    Base.metadata.create_all(pg_engine)
    _alembic("stamp", "head")
    assert _incident_tables(pg_engine) == ["incident_reports", "incidents"]

    _alembic("downgrade", "-1")
    assert _incident_tables(pg_engine) == []

    _alembic("upgrade", "head")
    assert _incident_tables(pg_engine) == ["incident_reports", "incidents"]


# -- 6-9. CRUD + rollback ------------------------------------------------------------


def test_failed_workflow_incident_has_no_report(db):
    repo = IncidentRepository(db)
    ev = make_event().model_dump(mode="json")
    incident, report = repo.persist_workflow_result(
        ev, _decision(status="llm_unavailable", severity=None),
        None, [],
    )
    assert incident.status == "llm_unavailable"
    assert incident.severity is None
    assert report is None


def test_transaction_rollback_on_report_failure(db, monkeypatch):
    repo = IncidentRepository(db)
    ev = make_event().model_dump(mode="json")

    def _boom(*a, **k):
        raise RuntimeError("report exploded")

    monkeypatch.setattr(repo, "create_report", _boom)
    with pytest.raises(RuntimeError):
        repo.persist_workflow_result(ev, _decision(), _analysis(), ["x"])
    # nothing half-created
    assert repo.count() == 0


# -- 10-11. workflow persistence via API -----------------------------------------------


def test_api_analyze_persists_incident_and_report(api_client):
    client, _, _ = api_client
    payload = make_event().model_dump(mode="json")
    r = client.post("/api/v1/incidents/analyze", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["incident_id"]

    # persisted incident
    r = client.get(f"/api/v1/incidents/{body['incident_id']}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["incident"]["zone_name"] == "server-room"
    assert detail["incident"]["severity"] == "HIGH"
    assert detail["incident"]["status"] == "completed"
    # event reconstruction
    assert detail["incident"]["event_data"]["tracking_id"] == 2
    assert detail["incident"]["event_data"]["camera_id"] == payload["camera_id"]
    # report exists
    assert detail["report"] is not None
    assert detail["report"]["severity"] == "HIGH"
    assert detail["report"]["reasoning"]


def test_api_analyze_failure_not_falsely_completed(api_client, monkeypatch):
    client, svc, _ = api_client
    from app.incidents.fake_llm import FakeAnalysisLLM
    from app.incidents.service import IncidentWorkflowService

    bad = IncidentWorkflowService(
        svc.lc_service, llm_factory=lambda: FakeAnalysisLLM("malformed")
    )
    app.dependency_overrides[get_incident_service] = lambda: bad
    r = client.post("/api/v1/incidents/analyze",
                    json=make_event().model_dump(mode="json"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "analysis_failed"
    assert body["incident_id"]  # failure observable...
    # ...but never a completed incident with a report
    r = client.get(f"/api/v1/incidents/{body['incident_id']}")
    assert r.json()["incident"]["status"] == "analysis_failed"
    assert r.json()["report"] is None


# -- 12-17. list + pagination + filters -----------------------------------------------


def _seed(client, n, **kw):
    ids = []
    for i in range(n):
        ev = make_event(zone_name=kw.get("zone_name", "server-room"),
                        tracking_id=100 + i).model_dump(mode="json")
        r = client.post("/api/v1/incidents/analyze", json=ev)
        assert r.status_code == 200
        ids.append(r.json()["incident_id"])
    return ids


def test_list_pagination(api_client):
    client, _, _ = api_client
    _seed(client, 5)
    r = client.get("/api/v1/incidents?page=1&page_size=2")
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2
    r = client.get("/api/v1/incidents?page=3&page_size=2")
    assert len(r.json()["items"]) == 1
    # newest first
    first = client.get("/api/v1/incidents?page=1&page_size=5").json()["items"]
    created = [i["created_at"] for i in first]
    assert created == sorted(created, reverse=True)


def test_list_filters(api_client):
    client, _, _ = api_client
    _seed(client, 2, zone_name="server-room")
    _seed(client, 1, zone_name="lobby")
    r = client.get("/api/v1/incidents?zone_name=lobby")
    assert r.json()["total"] == 1
    r = client.get("/api/v1/incidents?status=completed")
    assert r.json()["total"] == 3
    r = client.get("/api/v1/incidents?status=bogus")
    assert r.json()["total"] == 0
    r = client.get("/api/v1/incidents?severity=HIGH")
    assert r.json()["total"] == 3
    r = client.get("/api/v1/incidents?severity=LOW")
    assert r.json()["total"] == 0
    cam = client.get("/api/v1/incidents?page=1&page_size=1").json(
    )["items"][0]["camera_id"]
    r = client.get(f"/api/v1/incidents?camera_id={cam}")
    assert r.json()["total"] == 1


# -- 18-19. get incident / report ---------------------------------------------------------


def test_get_incident_and_report(api_client):
    client, _, _ = api_client
    ids = _seed(client, 1)
    r = client.get(f"/api/v1/incidents/{ids[0]}")
    assert r.status_code == 200
    assert r.json()["incident"]["id"] == ids[0]
    r = client.get(f"/api/v1/incidents/{ids[0]}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["incident_id"] == ids[0]
    assert body["title"].startswith("Zone Entry")
    assert body["cited_policy_chunk_ids"]
    r = client.get(f"/api/v1/incidents/{uuid.uuid4()}")
    assert r.status_code == 404
    r = client.get(f"/api/v1/incidents/{uuid.uuid4()}/report")
    assert r.status_code == 404


# -- 20-22. reprocess ---------------------------------------------------------------------------


def test_reprocess_updates_in_place(api_client):
    client, _, _ = api_client
    ids = _seed(client, 1)
    iid = ids[0]
    r = client.post(f"/api/v1/incidents/{iid}/reprocess")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["incident_id"] == iid  # same identity
    # still exactly one incident and one report
    r = client.get("/api/v1/incidents")
    assert r.json()["total"] == 1
    r = client.get(f"/api/v1/incidents/{iid}")
    assert r.json()["report"] is not None
    assert r.json()["incident"]["id"] == iid


def test_citation_preservation(api_client):
    client, _, _ = api_client
    ids = _seed(client, 1)
    detail = client.get(f"/api/v1/incidents/{ids[0]}").json()
    report = client.get(f"/api/v1/incidents/{ids[0]}/report").json()
    # citations persisted verbatim from the validated decision
    assert report["cited_policy_chunk_ids"]
    assert all("#" in c for c in report["cited_policy_chunk_ids"])
    # citation guard holds in storage: cited ⊆ retrieved
    assert set(report["cited_policy_chunk_ids"]) <= set(
        report["retrieved_chunk_ids"]
    )
    # report mirrors the incident outcome
    assert report["severity"] == detail["incident"]["severity"]
    assert report["summary"] == detail["incident"]["summary"]


# -- 23. policy change -> reindex -> reprocess ----------------------------------------------


def test_policy_reindex_reprocess_flow(api_client):
    client, svc, policies = api_client
    ids = _seed(client, 1)
    iid = ids[0]
    before = client.get(f"/api/v1/incidents/{iid}/report").json()

    # change a policy, reindex the service's RAG
    target = policies / "restricted-area-policy.md"
    original = target.read_text()
    target.write_text(original + "\n\n## Reprocess Note\nReprocessing sees this.\n")
    svc.lc_service.rag_service.reindex()

    r = client.post(f"/api/v1/incidents/{iid}/reprocess")
    assert r.status_code == 200
    after = client.get(f"/api/v1/incidents/{iid}/report").json()
    # same incident, refreshed report, citations still valid
    assert after["incident_id"] == iid
    assert set(after["cited_policy_chunk_ids"]) <= set(
        after["retrieved_chunk_ids"]
    )
    assert before["incident_id"] == after["incident_id"]
    target.write_text(original)  # restore


# -- health --------------------------------------------------------------------------------


def test_health_postgres_incidents(api_client):
    client, _, _ = api_client
    _seed(client, 1)
    r = client.get("/api/v1/health/detailed")
    assert r.status_code == 200
    comp = r.json()["postgres_incidents"]
    # health reports the real (dev) database, not the seeded test DB
    assert comp["status"] == "up"
    assert "alembic 20261007_0003 (current)" in comp["detail"]
