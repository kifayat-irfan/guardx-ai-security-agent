"""Server-sent events: live zone events + incident notifications (Phase 8).

GET /api/v1/events/stream — subscribe once; the frontend keeps a single
shared EventSource. Event types: `connected`, `zone_event`, `incident`.
A `: heartbeat` comment is sent every 20s to keep proxies alive.
"""
import json
import queue

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.events.bus import bus

router = APIRouter(tags=["events"])

_HEARTBEAT_SECONDS = 20


@router.get("/events/stream")
def stream_events():
    q = bus.subscribe()

    def gen():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    msg = q.get(timeout=_HEARTBEAT_SECONDS)
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                payload = json.dumps(msg["data"], default=str)
                yield f"event: {msg['type']}\ndata: {payload}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
