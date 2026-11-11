"""A tiny TTL cache so the terminal's polling never multiplies load on the
production platform. One upstream answer, many readers."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self, ttl_s: float):
        self.ttl_s = ttl_s
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key: str, fn: Callable[[], Any], ttl_s: float | None = None,
                       ttl_for: Callable[[Any], float] | None = None) -> Any:
        """`ttl_for(value)` lets the answer itself decide how long it may be reused
        (an incomplete answer must not be kept as long as a complete one)."""
        ttl = self.ttl_s if ttl_s is None else ttl_s
        now = time.monotonic()
        with self._lock:
            hit = self._store.get(key)
            if hit and hit[0] > now:
                self.hits += 1
                return hit[1]
        value = fn()
        if ttl_for is not None:
            ttl = ttl_for(value)
        with self._lock:
            self._store[key] = (now + ttl, value)
            self.misses += 1
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        return {"entries": len(self._store), "hits": self.hits, "misses": self.misses, "ttl_s": self.ttl_s}
