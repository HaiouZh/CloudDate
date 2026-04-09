"""
CloudDate — Collectors Package
Modular data collectors inspired by node_exporter's collector pattern.
Each collector is independent and reads from /proc, /sys, or system APIs.
"""

from server.collectors.cpu import collect_cpu
from server.collectors.memory import collect_memory
from server.collectors.disk import collect_disk_usage, collect_disk_io
from server.collectors.network import collect_network
from server.collectors.process import collect_processes
from server.collectors.docker_stats import collect_docker
from server.collectors.system_info import collect_system_info
from server.collectors.temperature import collect_temperature
from server.collectors.services import collect_services, collect_failed_services

__all__ = [
    "collect_cpu",
    "collect_memory",
    "collect_disk_usage",
    "collect_disk_io",
    "collect_network",
    "collect_processes",
    "collect_docker",
    "collect_system_info",
    "collect_temperature",
    "collect_services",
    "collect_failed_services",
]
