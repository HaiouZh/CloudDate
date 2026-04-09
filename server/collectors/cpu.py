"""
CloudDate — CPU Collector
Reads CPU usage from /proc/stat, similar to node_exporter's cpu_linux.go.
Uses psutil for cross-platform compatibility and percentage calculations.
"""

import psutil
from server.config import config


def collect_cpu() -> dict:
    """
    Collect CPU metrics.
    Returns total usage, per-core usage, and load averages.

    Inspired by node_exporter reading /proc/stat for per-CPU time breakdowns,
    but using psutil for simpler percentage-based output.
    """
    # Total CPU percent (blocking call with interval=0 uses cached delta)
    total_percent = psutil.cpu_percent(interval=0)

    # Per-core percentages
    per_core = psutil.cpu_percent(interval=0, percpu=True)

    # Load averages (1, 5, 15 min) — from /proc/loadavg
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        load_avg = [0.0, 0.0, 0.0]

    # CPU count
    cpu_count = psutil.cpu_count(logical=True)

    return {
        "total": round(total_percent, 1),
        "cores": [round(c, 1) for c in per_core],
        "core_count": cpu_count,
        "load_avg": [round(l, 2) for l in load_avg],
    }
