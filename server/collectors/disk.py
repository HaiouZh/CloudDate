"""
CloudDate — Disk Collector
Collects disk usage and I/O statistics.
Inspired by node_exporter's diskstats_linux.go (I/O) and filesystem_linux.go (usage).
"""

import psutil

# Track previous disk I/O counters for rate calculation
_prev_disk_io = None
_prev_disk_time = None


def collect_disk_usage() -> list[dict]:
    """
    Collect disk partition usage (mounted filesystems).
    Similar to node_exporter's filesystem collector reading mount points.
    """
    partitions = psutil.disk_partitions(all=False)
    disks = []

    for part in partitions:
        # Skip pseudo/virtual filesystems
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.percent, 1),
            })
        except (PermissionError, OSError):
            continue

    return disks


def collect_disk_io() -> dict:
    """
    Collect disk I/O rates (bytes/sec).
    Similar to node_exporter's diskstats collector reading /proc/diskstats.
    Returns read/write rates calculated from delta between calls.
    """
    import time

    global _prev_disk_io, _prev_disk_time

    try:
        counters = psutil.disk_io_counters()
    except Exception:
        return {"read_rate": 0, "write_rate": 0, "read_total": 0, "write_total": 0}

    if counters is None:
        return {"read_rate": 0, "write_rate": 0, "read_total": 0, "write_total": 0}

    now = time.time()
    result = {
        "read_total": counters.read_bytes,
        "write_total": counters.write_bytes,
        "read_rate": 0,
        "write_rate": 0,
    }

    if _prev_disk_io is not None and _prev_disk_time is not None:
        dt = now - _prev_disk_time
        if dt > 0:
            result["read_rate"] = int((counters.read_bytes - _prev_disk_io.read_bytes) / dt)
            result["write_rate"] = int((counters.write_bytes - _prev_disk_io.write_bytes) / dt)
            # Clamp negative values (can happen on counter reset)
            result["read_rate"] = max(0, result["read_rate"])
            result["write_rate"] = max(0, result["write_rate"])

    _prev_disk_io = counters
    _prev_disk_time = now

    return result
