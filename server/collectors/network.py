"""
CloudDate — Network Collector
Collects per-interface network I/O rates.
Inspired by node_exporter's netdev_linux.go reading /proc/net/dev.
"""

import time
import psutil

# Track previous network I/O counters for rate calculation
_prev_net_io = None
_prev_net_time = None


def collect_network() -> dict:
    """
    Collect per-interface network traffic rates (bytes/sec).
    Calculates delta from previous reading, similar to how
    node_exporter computes network interface statistics.
    """
    global _prev_net_io, _prev_net_time

    try:
        counters = psutil.net_io_counters(pernic=True)
    except Exception:
        return {}

    now = time.time()
    result = {}

    for iface, stats in counters.items():
        # Skip loopback and docker-internal interfaces for cleaner display
        if iface.startswith(("lo", "veth")):
            continue

        entry = {
            "rx_bytes": stats.bytes_recv,
            "tx_bytes": stats.bytes_sent,
            "rx_rate": 0,
            "tx_rate": 0,
        }

        if _prev_net_io is not None and _prev_net_time is not None and iface in _prev_net_io:
            dt = now - _prev_net_time
            if dt > 0:
                prev = _prev_net_io[iface]
                entry["rx_rate"] = max(0, int((stats.bytes_recv - prev.bytes_recv) / dt))
                entry["tx_rate"] = max(0, int((stats.bytes_sent - prev.bytes_sent) / dt))

        result[iface] = entry

    _prev_net_io = counters
    _prev_net_time = now

    return result
