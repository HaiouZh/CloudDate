"""
CloudDate — Memory Collector
Reads memory and swap usage, inspired by node_exporter's meminfo_linux.go.
The reference reads /proc/meminfo fields individually; we use psutil for convenience.
"""

import psutil


def collect_memory() -> dict:
    """
    Collect memory and swap metrics.
    Returns total, used, available, cached, buffers, and percentages.
    """
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "cached": getattr(mem, "cached", 0),
            "buffers": getattr(mem, "buffers", 0),
            "percent": round(mem.percent, 1),
            "free": mem.free,
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": round(swap.percent, 1),
        },
    }
