"""
CloudDate — System Info Collector
Collects static system information (hostname, kernel, OS, CPU model, etc.).
Similar to node_exporter's uname and os_release collectors.
"""

import platform
import socket
import time
import psutil
from server.config import config


def collect_system_info() -> dict:
    """
    Collect static system information.
    This is called once per WebSocket connection, not on every tick.
    """
    # CPU model from /proc/cpuinfo
    cpu_model = _get_cpu_model()

    # OS release info
    os_info = _get_os_release()

    # Boot time and uptime
    boot_time = psutil.boot_time()
    uptime = int(time.time() - boot_time)

    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "os": os_info,
        "cpu_model": cpu_model,
        "cpu_cores_physical": psutil.cpu_count(logical=False) or 0,
        "cpu_cores_logical": psutil.cpu_count(logical=True) or 0,
        "total_memory": psutil.virtual_memory().total,
        "total_swap": psutil.swap_memory().total,
        "boot_time": boot_time,
        "uptime": uptime,
    }


def _get_cpu_model() -> str:
    """Read CPU model name, mimicking node_exporter's cpuinfo reading."""
    try:
        # Try reading from /proc/cpuinfo (Linux)
        proc_path = config.HOST_PROC
        with open(f"{proc_path}/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (FileNotFoundError, PermissionError):
        pass

    # Fallback
    return platform.processor() or "Unknown"


def _get_os_release() -> str:
    """Read OS release info, similar to node_exporter's os_release collector."""
    # Try /etc/os-release (standard on most Linux distros)
    for path in [
        f"{config.HOST_ETC}/os-release",
        "/etc/os-release",
        "/usr/lib/os-release",
    ]:
        try:
            with open(path, "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except (FileNotFoundError, PermissionError):
            continue

    return f"{platform.system()} {platform.release()}"
