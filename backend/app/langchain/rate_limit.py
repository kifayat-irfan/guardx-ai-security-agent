"""Per-minute rate limiter for paid/quota-limited LLM APIs.

GuardX's SenseNova plan allows ~1500 calls / 5h, but the API also enforces
a per-minute ceiling: on 2026-10-11 a crowded test video (11+ people in
frame) produced a burst of zone events, each spawning one LangGraph
incident workflow and one SenseNova call, and the API answered HTTP 429
``rpm exhausted``. Those analyses failed honestly (``analysis_failed``),
but a supervisor demo should not show a wall of failures.

This module implements a process-wide token bucket so the backend never
sends SenseNova more than ``SENSENOVA_RPM_LIMIT`` calls per minute. When
the budget is exhausted the ``analyze_event`` node records an honest
``rate_limited`` status instead of burning quota on a call the API would
reject; the dashboard's existing re-run path can retry the incident once
the minute rolls over.

Pure stdlib, no network: safe to unit test.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class RateLimiter:
    """Thread-safe token bucket.

    ``calls_per_minute`` tokens are refilled continuously (one token every
    ``60 / calls_per_minute`` seconds), up to a burst capacity equal to
    ``calls_per_minute``. ``acquire()`` takes one token when available and
    returns True; it returns False immediately (no waiting) when empty.
    """

    def __init__(self, calls_per_minute: int,
                 clock: Callable[[], float] | None = None) -> None:
        if calls_per_minute < 0:
            raise ValueError("calls_per_minute must be >= 0")
        self.calls_per_minute = calls_per_minute
        self._clock = clock or time.monotonic
        self._tokens = float(calls_per_minute)
        self._last = self._clock()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Take one token if available. Never blocks."""
        if self.calls_per_minute == 0:
            return False
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._last)
            self._last = now
            # continuous refill, capped at one full minute of budget
            self._tokens = min(
                float(self.calls_per_minute),
                self._tokens + elapsed * (self.calls_per_minute / 60.0),
            )
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    @property
    def available(self) -> float:
        """Tokens currently available (for health/debug; no mutation)."""
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._last)
            return min(
                float(self.calls_per_minute),
                self._tokens + elapsed * (self.calls_per_minute / 60.0),
            )


_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def get_sensenova_limiter() -> RateLimiter:
    """Process-wide SenseNova rate limiter, configured from settings.

    Reads ``sensenova_rpm_limit`` (env ``SENSENOVA_RPM_LIMIT``, default 20).
    ``0`` disables the guard (unlimited); any change needs a backend restart.
    """
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                from app.core.config import get_settings

                rpm = int(getattr(get_settings(), "sensenova_rpm_limit", 20))
                _limiter = RateLimiter(max(0, rpm))
    return _limiter
