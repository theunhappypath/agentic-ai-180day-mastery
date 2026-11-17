"""Bounded-retry HTTP fetcher with a token bucket.

Deliberately ordinary production Python: type hints, dataclasses, logging,
nested control flow, dunder methods, decorators, f-strings. The punctuation
density and identifier style are the point, not the logic.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
DEFAULT_TIMEOUT_S = 10.0


class RateLimited(Exception):
    """Raised when the local bucket refuses to issue a token in time."""

    def __init__(self, waited_s: float) -> None:
        super().__init__(f"rate limited after waiting {waited_s:.3f}s")
        self.waited_s = waited_s


@dataclass
class TokenBucket:
    """Classic leaky-bucket limiter. Thread-safe, monotonic-clock based."""

    capacity: float
    refill_per_second: float
    _tokens: float = field(init=False)
    _updated_at: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_second <= 0:
            raise ValueError("capacity and refill_per_second must be positive")
        self._tokens = self.capacity
        self._updated_at = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated_at
        if elapsed > 0:
            self._tokens = min(
                self.capacity, self._tokens + elapsed * self.refill_per_second
            )
            self._updated_at = now

    def acquire(self, tokens: float = 1.0, max_wait_s: float = 5.0) -> float:
        deadline = time.monotonic() + max_wait_s
        waited = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                shortfall = tokens - self._tokens
                sleep_for = shortfall / self.refill_per_second
            if time.monotonic() + sleep_for > deadline:
                raise RateLimited(waited)
            time.sleep(sleep_for)
            waited += sleep_for

    def __repr__(self) -> str:
        return f"<TokenBucket {self._tokens:.2f}/{self.capacity:.0f}>"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_s: float = 0.25
    max_delay_s: float = 8.0
    jitter: float = 0.3

    def delay_for(self, attempt: int) -> float:
        raw = min(self.base_delay_s * (2 ** attempt), self.max_delay_s)
        return raw * (1.0 + random.uniform(-self.jitter, self.jitter))

    def should_retry(self, attempt: int, status: int | None, exc: Exception | None) -> bool:
        if attempt + 1 >= self.max_attempts:
            return False
        if exc is not None:
            return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout))
        return status in RETRYABLE_STATUS


class Fetcher:
    def __init__(
        self,
        base_url: str,
        *,
        bucket: TokenBucket | None = None,
        policy: RetryPolicy | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.policy = policy or RetryPolicy()
        self.bucket = bucket or TokenBucket(capacity=20, refill_per_second=10)
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=dict(headers or {}),
            timeout=timeout_s,
        )

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_json(self, path: str, **params: Any) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.policy.max_attempts):
            self.bucket.acquire()
            status: int | None = None
            try:
                response = self._client.get(path, params=params or None)
                status = response.status_code
                if status < 400:
                    return response.json()
                logger.warning("GET %s -> %s (attempt %d)", path, status, attempt + 1)
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                logger.warning("GET %s failed: %r (attempt %d)", path, exc, attempt + 1)

            if not self.policy.should_retry(attempt, status, last_exc):
                break
            time.sleep(self.policy.delay_for(attempt))

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"GET {path!r} exhausted {self.policy.max_attempts} attempts")

    def map_paths(self, paths: Iterable[str], fn: Callable[[dict], Any]) -> list[Any]:
        return [fn(self.get_json(p)) for p in paths]