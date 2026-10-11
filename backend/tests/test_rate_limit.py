"""Unit tests for the SenseNova per-minute rate limiter.

No network, no backend imports: the limiter is pure stdlib logic with an
injectable clock.
"""
from __future__ import annotations

import threading

import pytest

from app.langchain.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_full_burst_then_empty() -> None:
    clock = FakeClock()
    limiter = RateLimiter(60, clock=clock)  # 1 token/sec
    assert all(limiter.acquire() for _ in range(60))
    assert limiter.acquire() is False


def test_continuous_refill() -> None:
    clock = FakeClock()
    limiter = RateLimiter(60, clock=clock)
    for _ in range(60):
        assert limiter.acquire()
    assert limiter.acquire() is False
    clock.advance(30.0)  # half a minute -> 30 tokens
    assert all(limiter.acquire() for _ in range(30))
    assert limiter.acquire() is False


def test_refill_capped_at_burst() -> None:
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock)
    clock.advance(3600.0)  # idle an hour: still only 10 tokens
    assert all(limiter.acquire() for _ in range(10))
    assert limiter.acquire() is False


def test_zero_limit_denies_everything() -> None:
    clock = FakeClock()
    limiter = RateLimiter(0, clock=clock)
    assert limiter.acquire() is False


def test_negative_limit_rejected() -> None:
    with pytest.raises(ValueError):
        RateLimiter(-1)


def test_thread_safe_under_burst() -> None:
    clock = FakeClock()
    limiter = RateLimiter(100, clock=clock)
    granted = []
    threads = [
        threading.Thread(target=lambda: granted.append(limiter.acquire()))
        for _ in range(200)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(granted) == 100  # never over-grants
