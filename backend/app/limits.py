"""Per-visitor rate limiting, held in memory.

Good for a single server process. Several processes would each keep their own counts, so a
bigger deployment would move this to Redis.
"""

import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

# How many visitors to remember before clearing out the ones whose requests have expired.
_SWEEP_THRESHOLD = 10_000


class RateLimiter:
    """Allow `limit` requests per key in any `window_seconds`-long stretch (sliding window)."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def retry_after(self, key: str) -> float | None:
        """Record a request. Returns None if it's allowed, or the seconds until one will be."""
        if self.limit <= 0:
            return None
        now = self._clock()
        if len(self._hits) > _SWEEP_THRESHOLD:
            self._sweep(now)

        hits = self._hits.setdefault(key, deque())
        self._expire(hits, now)
        if len(hits) >= self.limit:
            return hits[0] + self.window_seconds - now
        hits.append(now)
        return None

    def _expire(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        for key in list(self._hits):
            self._expire(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]


def client_ip(request: Request, proxy_hops: int) -> str:
    """The visitor's address.

    Behind a reverse proxy the socket address is the proxy's, and the real one is in
    X-Forwarded-For. Visitors can put anything they like at the front of that header, so
    only the entries added by our own proxies (the last `proxy_hops`) are trusted.
    """
    if proxy_hops > 0:
        forwarded = [
            part.strip()
            for part in request.headers.get("x-forwarded-for", "").split(",")
            if part.strip()
        ]
        if len(forwarded) >= proxy_hops:
            return forwarded[-proxy_hops]
    return request.client.host if request.client else "unknown"
