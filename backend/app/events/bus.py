"""In-process event bus for the live dashboard stream (Phase 8).

Publishers: camera workers (zone_event), incidents API (incident).
Consumers: SSE endpoint subscribers. Thread-safe; slow consumers drop
messages instead of blocking publishers.
"""
from __future__ import annotations

import queue
import threading
from typing import Any


class EventBus:
    def __init__(self, maxsize: int = 500):
        self._subs: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, event_type: str, data: dict[str, Any]) -> int:
        """Publish to all subscribers. Returns subscriber count reached."""
        msg = {"type": event_type, "data": data}
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass  # slow consumer: drop, never block the publisher
        return len(subs)


bus = EventBus()
