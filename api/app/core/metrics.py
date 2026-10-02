import time
from collections import deque
from datetime import UTC, datetime


class LatencyTracker:
    def __init__(self, size: int = 1000) -> None:
        self._samples: deque[float] = deque(maxlen=size)

    def record(self, ms: float) -> None:
        self._samples.append(ms)

    def snapshot(self) -> dict[str, float | int]:
        samples = sorted(self._samples)
        if not samples:
            return {"samples": 0, "avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
        return {
            "samples": len(samples),
            "avg_ms": round(sum(samples) / len(samples), 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(samples[-1], 2),
        }


latency = LatencyTracker()
STARTED_AT = datetime.now(UTC)
_started_monotonic = time.monotonic()


def uptime_seconds() -> int:
    return int(time.monotonic() - _started_monotonic)
