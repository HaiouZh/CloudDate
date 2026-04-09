"""
CloudDate — Ring Buffer (Circular Buffer)
Fixed-size in-memory buffer for time-series metric storage.
Inspired by Netdata's tiered storage approach but simplified to a single in-memory tier.
"""

import threading
import time
from collections import deque
from typing import Any


class RingBuffer:
    """Thread-safe fixed-size circular buffer for storing time-series data points."""

    def __init__(self, max_size: int = 3600):
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self.max_size = max_size

    def append(self, data: dict[str, Any]) -> None:
        """Add a data point with automatic timestamp."""
        entry = {
            "timestamp": time.time(),
            "data": data,
        }
        with self._lock:
            self._buffer.append(entry)

    def get_latest(self, n: int = 1) -> list[dict]:
        """Get the latest N data points."""
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)
            return list(self._buffer)[-n:]

    def get_since(self, since_timestamp: float) -> list[dict]:
        """Get all data points since a given timestamp."""
        with self._lock:
            return [
                entry for entry in self._buffer
                if entry["timestamp"] >= since_timestamp
            ]

    def get_all(self) -> list[dict]:
        """Get all data points in the buffer."""
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Clear all data from the buffer."""
        with self._lock:
            self._buffer.clear()

    @property
    def size(self) -> int:
        """Current number of entries in the buffer."""
        with self._lock:
            return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        return self.size == 0


class MetricsStore:
    """
    Central store for all metric buffers.
    Manages separate ring buffers for fast metrics (CPU, memory, etc.)
    and slow metrics (processes, docker, etc.).
    """

    def __init__(self, buffer_size: int = 3600):
        self.fast_metrics = RingBuffer(buffer_size)   # CPU, memory, swap, network, load, disk IO
        self.slow_metrics = RingBuffer(buffer_size)   # Processes, docker, disk usage, temperature

    def clear_all(self) -> None:
        self.fast_metrics.clear()
        self.slow_metrics.clear()
