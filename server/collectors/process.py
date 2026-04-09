"""
CloudDate — Process Collector
Collects top processes by CPU/memory usage.
Inspired by Netdata's process monitoring that provides per-process resource tracking.
"""

import psutil
from server.config import config


def collect_processes() -> list[dict]:
    """
    Collect top processes sorted by CPU usage.
    Returns a list of process dicts with PID, name, CPU%, MEM%, user, status.
    Limited to config.PROCESS_LIMIT entries for performance.
    """
    procs = []

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "username", "status"]):
        try:
            info = proc.info
            # Filter out kernel threads and idle processes
            if info["cpu_percent"] is None:
                continue
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "cpu": round(info["cpu_percent"], 1),
                "mem": round(info["memory_percent"] or 0, 1),
                "user": info["username"] or "system",
                "status": info["status"] or "unknown",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort by CPU usage descending, then by memory
    procs.sort(key=lambda p: (p["cpu"], p["mem"]), reverse=True)

    return procs[:config.PROCESS_LIMIT]
