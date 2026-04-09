"""
CloudDate — Systemd Service Collector
Collects systemd service unit status via subprocess (systemctl).
Only works on Linux systems with systemd.
"""

import logging
import subprocess
import re

logger = logging.getLogger("clouddate.services")

# Cache the subprocess availability check
_systemctl_available = None


def _check_systemctl() -> bool:
    """Check if systemctl is available on this system."""
    global _systemctl_available
    if _systemctl_available is not None:
        return _systemctl_available
    try:
        subprocess.run(
            ["systemctl", "--version"],
            capture_output=True, timeout=5
        )
        _systemctl_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _systemctl_available = False
        logger.info("systemctl not available — service monitoring disabled")
    return _systemctl_available


def collect_services(filter_type: str = "service") -> list[dict]:
    """
    Collect systemd service unit status.

    Returns a list of dicts:
    [
        {
            "name": "nginx.service",
            "load": "loaded",
            "active": "active",
            "sub": "running",
            "description": "A high performance web server..."
        },
        ...
    ]

    Only returns loaded services by default (ignores not-found / masked unless active).
    """
    if not _check_systemctl():
        return []

    try:
        result = subprocess.run(
            [
                "systemctl", "list-units",
                f"--type={filter_type}",
                "--all",
                "--no-pager",
                "--no-legend",
                "--plain",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode not in (0, 1):  # 1 = some units inactive, still valid
            return []

        services = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue

            # Parse: UNIT LOAD ACTIVE SUB DESCRIPTION...
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue

            unit_name = parts[0]
            load_state = parts[1]
            active_state = parts[2]
            sub_state = parts[3]
            description = parts[4] if len(parts) > 4 else ""

            # Skip not-found / masked units that are inactive
            if load_state in ("not-found", "masked") and active_state == "inactive":
                continue

            services.append({
                "name": unit_name,
                "load": load_state,
                "active": active_state,
                "sub": sub_state,
                "description": description,
            })

        # Sort: active/running first, then failed, then inactive
        priority = {"active": 0, "failed": 1, "activating": 2, "deactivating": 3, "inactive": 4}
        services.sort(key=lambda s: (priority.get(s["active"], 5), s["name"]))

        return services

    except subprocess.TimeoutExpired:
        logger.warning("systemctl timed out")
        return []
    except Exception as e:
        logger.error(f"Failed to collect services: {e}")
        return []


def collect_failed_services() -> list[dict]:
    """Collect only failed systemd services (lightweight check)."""
    if not _check_systemctl():
        return []

    try:
        result = subprocess.run(
            [
                "systemctl", "list-units",
                "--type=service",
                "--state=failed",
                "--no-pager",
                "--no-legend",
                "--plain",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        failed = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split(None, 4)
            if len(parts) >= 4:
                failed.append({
                    "name": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": parts[4] if len(parts) > 4 else "",
                })

        return failed

    except Exception as e:
        logger.error(f"Failed to collect failed services: {e}")
        return []
