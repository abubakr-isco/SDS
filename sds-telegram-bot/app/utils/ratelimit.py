from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Hashable


class SlidingWindowLimiter:
    """In-memory per-key rate limiter (single bot process)."""

    def __init__(self, max_events: int, window_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._clock = clock
        self._events: dict[Hashable, deque[float]] = {}

    def hit(self, key: Hashable) -> bool:
        """Record an event. Returns False if the key is over the limit (event not recorded)."""
        now = self._clock()
        events = self._events.setdefault(key, deque())
        while events and now - events[0] >= self.window:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        if len(self._events) > 10_000:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        for key in [k for k, ev in self._events.items() if not ev or now - ev[-1] >= self.window]:
            del self._events[key]
