"""
agentphased.bus -- In-process pub/sub event bus.

Thread-safe, synchronous dispatch. Subscribers are called in registration
order. Every published event is retained in an append-only history for
debugging and testing.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional


class EventBus:
    """Minimal in-process pub/sub system."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = defaultdict(list)
        self._history: List[dict] = []

    # -- public API ----------------------------------------------------------

    def subscribe(self, topic: str, callback: Callable[[dict], None]) -> None:
        """Register *callback* to be invoked whenever *topic* is published."""
        with self._lock:
            self._subscribers[topic].append(callback)

    def publish(self, topic: str, payload: dict) -> None:
        """Dispatch *payload* to every subscriber of *topic*.

        The event is appended to the history list regardless of whether
        any subscribers exist.
        """
        event: dict = {
            "topic": topic,
            "timestamp": time.time(),
            **payload,
        }
        with self._lock:
            self._history.append(event)
            callbacks = list(self._subscribers.get(topic, []))

        for cb in callbacks:
            cb(event)

    def clear(self) -> None:
        """Remove all subscribers and clear event history."""
        with self._lock:
            self._subscribers.clear()
            self._history.clear()

    def history(self, topic: Optional[str] = None) -> List[dict]:
        """Return published events, optionally filtered by *topic*."""
        with self._lock:
            if topic is None:
                return list(self._history)
            return [e for e in self._history if e.get("topic") == topic]
