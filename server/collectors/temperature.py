"""
CloudDate — Temperature Collector
Reads hardware temperature sensors.
Inspired by node_exporter's hwmon_linux.go reading /sys/class/hwmon/.
"""

import psutil
import logging

logger = logging.getLogger("clouddate.temperature")


def collect_temperature() -> list[dict]:
    """
    Collect temperature sensor readings.
    Uses psutil.sensors_temperatures() which reads from /sys/class/hwmon/
    similar to node_exporter's hwmon collector.
    """
    temps = []

    try:
        sensor_data = psutil.sensors_temperatures()
        if not sensor_data:
            return temps

        for chip_name, entries in sensor_data.items():
            for entry in entries:
                temps.append({
                    "chip": chip_name,
                    "label": entry.label or chip_name,
                    "current": round(entry.current, 1),
                    "high": round(entry.high, 1) if entry.high else None,
                    "critical": round(entry.critical, 1) if entry.critical else None,
                })
    except (AttributeError, OSError) as e:
        # sensors_temperatures() is not available on all platforms
        logger.debug(f"Temperature sensors not available: {e}")

    return temps
