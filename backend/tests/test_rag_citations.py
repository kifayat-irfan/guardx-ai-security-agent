"""Citation integrity + zone-event query conversion (Phase 4)."""
import uuid

from app.rag.citations import invalid_citations, validate_citations
from app.rag.event_query import describe_event, zone_event_to_query
from app.zone_engine.events import ZoneEvent, ZoneEventType


def _event(**kw):
    base = dict(
        camera_id=uuid.uuid4(),
        zone_id=uuid.uuid4(),
        zone_name="server-room",
        tracking_id=2,
        event_type=ZoneEventType.ZONE_ENTER,
        timestamp=12.5,
        confidence=0.87,
        bounding_box=[0.4, 0.5, 0.6, 0.9],
        point=[0.5, 0.9],
        metadata={"dwell_elapsed": 3.2},
    )
    base.update(kw)
    return ZoneEvent(**base)


def test_event_to_query_mentions_zone_and_action():
    q = zone_event_to_query(_event())
    assert "server room" in q
    assert "entered" in q
    assert "restricted" in q.lower()


def test_event_to_query_exit_variant():
    q = zone_event_to_query(_event(event_type=ZoneEventType.ZONE_EXIT))
    assert "exited" in q


def test_event_to_query_has_no_decision():
    q = zone_event_to_query(_event()).lower()
    for word in ("severity is", "must dispatch", "high severity", "arrest"):
        assert word not in q  # retrieval query, not a decision


def test_describe_event_structure():
    d = describe_event(_event())
    assert d["zone_name"] == "server-room"
    assert d["event_type"] == "zone_enter"
    assert d["tracking_id"] == 2


def test_citation_validation_pass():
    retrieved = {"a#purpose", "b#rules", "c#response"}
    assert validate_citations(retrieved, {"a#purpose", "c#response"}) is True
    assert validate_citations(retrieved, set()) is True


def test_citation_validation_fails_on_hallucinated_chunk():
    retrieved = {"a#purpose", "b#rules"}
    assert validate_citations(retrieved, {"a#purpose", "zzz#fake"}) is False
    assert invalid_citations(retrieved, {"a#purpose", "zzz#fake"}) == {"zzz#fake"}
    assert invalid_citations(retrieved, {"a#purpose"}) == set()
