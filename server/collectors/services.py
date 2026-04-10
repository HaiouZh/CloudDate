"""
CloudDate — Systemd Service Collector
Collects systemd service unit status.

Detection strategy (in order):
1. Native `systemctl` — for direct deployment on host
2. `nsenter -t 1 -m -u` via host PID namespace — for Docker with `pid: host`
3. Graceful fallback — return empty list on non-systemd / non-Linux systems
"""

import logging
import os
import shutil
import subprocess
import time

logger = logging.getLogger("clouddate.services")

# Cache the command prefix (determined once on first call)
_cmd_prefix = None
_available = None

# Service results cache (avoid repeated expensive nsenter calls)
_services_cache = None
_services_cache_time = 0.0


def _detect_systemctl() -> tuple[bool, list[str]]:
    """
    Detect how to reach systemctl.
    Returns (available, command_prefix).
    """
    # Strategy 1: Native systemctl (direct host deployment)
    if shutil.which("systemctl"):
        try:
            r = subprocess.run(
                ["systemctl", "--version"],
                capture_output=True, timeout=5,
            )
            if r.returncode == 0:
                logger.info("Using native systemctl")
                return True, ["systemctl"]
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Strategy 2: nsenter into host PID 1 namespace (Docker with pid:host)
    # Check if PID 1 is accessible (requires pid: "host" in docker-compose)
    if os.path.exists("/proc/1/ns/mnt"):
        try:
            r = subprocess.run(
                ["nsenter", "-t", "1", "-m", "-u", "systemctl", "--version"],
                capture_output=True, timeout=5,
            )
            if r.returncode == 0:
                logger.info("Using nsenter to access host systemctl")
                return True, ["nsenter", "-t", "1", "-m", "-u", "systemctl"]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    logger.info("systemctl not available — service monitoring disabled")
    return False, []


def _get_cmd_prefix() -> list[str]:
    """Get the cached command prefix for systemctl access."""
    global _cmd_prefix, _available
    if _available is None:
        _available, _cmd_prefix = _detect_systemctl()
    return _cmd_prefix if _available else []


def _run_systemctl(*args, timeout: int = 10) -> subprocess.CompletedProcess | None:
    """Run a systemctl command using the detected access method."""
    prefix = _get_cmd_prefix()
    if not prefix:
        return None

    try:
        return subprocess.run(
            prefix + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning(f"systemctl command failed: {e}")
        return None


def _parse_units(output: str) -> list[dict]:
    """Parse systemctl list-units output into structured data."""
    services = []
    for line in output.strip().split('\n'):
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

    return services


def collect_services(filter_type: str = "service") -> list[dict]:
    """
    Collect systemd service unit status.

    Returns a sorted list of service dicts with name, load, active, sub, description.
    Active/running services first, then failed, then inactive.

    Results are cached for 60 seconds to avoid repeated expensive nsenter calls.
    """
    global _services_cache, _services_cache_time
    now = time.time()
    if _services_cache is not None and (now - _services_cache_time) < 60:
        return _services_cache

    result = _run_systemctl(
        "list-units",
        f"--type={filter_type}",
        "--all",
        "--no-pager",
        "--no-legend",
        "--plain",
    )

    if result is None or result.returncode not in (0, 1):
        return []

    services = _parse_units(result.stdout)

    # Sort: active/running first, then failed, then inactive
    priority = {"active": 0, "failed": 1, "activating": 2, "deactivating": 3, "inactive": 4}
    services.sort(key=lambda s: (priority.get(s["active"], 5), s["name"]))

    _services_cache = services
    _services_cache_time = now
    return services


def collect_failed_services() -> list[dict]:
    """Collect only failed systemd services (lightweight check)."""
    result = _run_systemctl(
        "list-units",
        "--type=service",
        "--state=failed",
        "--no-pager",
        "--no-legend",
        "--plain",
    )

    if result is None:
        return []

    return _parse_units(result.stdout)
