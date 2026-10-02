"""Lightweight in-process metrics registry.

Counters and latency observations aggregated across games. Exposed via
``GET /api/metrics``. Swappable for Prometheus without touching call sites.
"""

from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[str] = Counter()
        self._latencies: dict[str, list[float]] = {}

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe_latency(self, name: str, ms: float) -> None:
        with self._lock:
            self._latencies.setdefault(name, []).append(ms)

    def snapshot(self) -> dict:
        with self._lock:
            latency_stats = {}
            for name, values in self._latencies.items():
                ordered = sorted(values)
                p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] if ordered else 0.0
                latency_stats[name] = {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 1) if values else 0.0,
                    "p95_ms": round(p95, 1),
                }
            return {"counters": dict(self._counters), "latencies": latency_stats}


metrics = MetricsRegistry()
