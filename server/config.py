"""
CloudDate — Configuration Management
Centralized configuration with environment variable overrides.
"""

import os


class Config:
    """Application configuration with env var overrides."""

    # Server
    PORT: int = int(os.getenv("PORT", "5001"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    TOKEN: str = os.getenv("TOKEN", "")

    # Host filesystem paths (for Docker container mode)
    HOST_PROC: str = os.getenv("HOST_PROC", "/proc")
    HOST_SYS: str = os.getenv("HOST_SYS", "/sys")
    HOST_ETC: str = os.getenv("HOST_ETC", "/etc")

    # Ring buffer size (number of data points to keep)
    RING_BUFFER_SIZE: int = int(os.getenv("RING_BUFFER_SIZE", "3600"))

    # Refresh intervals (seconds)
    DEFAULT_INTERVAL: float = 2.0
    MIN_FAST_INTERVAL: float = 0.5    # CPU, memory, swap, network, load
    MIN_SLOW_INTERVAL: float = 3.0    # Processes, Docker, disk usage, temperature
    MAX_INTERVAL: float = 30.0

    # Sleep mode
    SLEEP_DELAY: float = float(os.getenv("SLEEP_DELAY", "30"))  # seconds before sleeping

    # Alert thresholds
    ALERT_CPU_PERCENT: float = float(os.getenv("ALERT_CPU", "90"))
    ALERT_MEMORY_PERCENT: float = float(os.getenv("ALERT_MEM", "90"))
    ALERT_SWAP_PERCENT: float = float(os.getenv("ALERT_SWAP", "80"))
    ALERT_DISK_PERCENT: float = float(os.getenv("ALERT_DISK", "90"))

    # Process list
    PROCESS_LIMIT: int = int(os.getenv("PROCESS_LIMIT", "50"))


config = Config()
