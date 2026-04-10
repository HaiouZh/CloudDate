"""
CloudDate — Scheduler
Manages the data collection loops with different frequencies.
Fast metrics (CPU, memory, etc.) run at user-requested interval.
Slow metrics (processes, docker, etc.) run at max(user_interval, 3s).
"""

import asyncio
import logging
import time

from server.config import config
from server.ring_buffer import MetricsStore
from server.connection_manager import ConnectionManager
from server.collectors.cpu import collect_cpu
from server.collectors.memory import collect_memory
from server.collectors.disk import collect_disk_usage, collect_disk_io
from server.collectors.network import collect_network
from server.collectors.process import collect_processes
from server.collectors.docker_stats import collect_docker
from server.collectors.temperature import collect_temperature
from server.collectors.services import collect_services

logger = logging.getLogger("clouddate.scheduler")


class Scheduler:
    """
    Orchestrates data collection and broadcasting.
    Two independent loops:
    - fast_loop: CPU, memory, swap, network, load, disk IO
    - slow_loop: processes, docker, disk usage, temperature
    """

    def __init__(self, store: MetricsStore, manager: ConnectionManager):
        self.store = store
        self.manager = manager
        self._running = False
        self._fast_task: asyncio.Task | None = None
        self._slow_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the collection scheduler."""
        self._running = True
        self._fast_task = asyncio.create_task(self._fast_loop())
        self._slow_task = asyncio.create_task(self._slow_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the collection scheduler."""
        self._running = False
        if self._fast_task:
            self._fast_task.cancel()
        if self._slow_task:
            self._slow_task.cancel()
        logger.info("Scheduler stopped")

    async def _fast_loop(self) -> None:
        """
        Fast collection loop for CPU, memory, swap, network, load, disk IO.
        Runs at the minimum client-requested interval (≥ 0.5s).
        Sleeps when no clients are connected.
        """
        # Prime the CPU percent cache (first call always returns 0)
        import psutil
        psutil.cpu_percent(interval=0, percpu=True)

        while self._running:
            try:
                # Sleep if no clients
                if self.manager.is_sleeping:
                    logger.debug("Fast loop sleeping...")
                    await self.manager.wait_for_wake()
                    logger.debug("Fast loop waking up")
                    # Re-prime CPU stats after wake
                    psutil.cpu_percent(interval=0, percpu=True)
                    await asyncio.sleep(0.5)

                # Collect fast metrics
                start = time.time()

                cpu_data = await asyncio.get_event_loop().run_in_executor(None, collect_cpu)
                mem_data = await asyncio.get_event_loop().run_in_executor(None, collect_memory)
                net_data = await asyncio.get_event_loop().run_in_executor(None, collect_network)
                disk_io = await asyncio.get_event_loop().run_in_executor(None, collect_disk_io)

                fast_data = {
                    "cpu": cpu_data,
                    **mem_data,
                    "network": net_data,
                    "disk_io": disk_io,
                }

                # Store in ring buffer
                self.store.fast_metrics.append(fast_data)

                # Check alert thresholds
                alerts = _check_alerts(fast_data)

                # Broadcast to all clients
                message = {
                    "type": "metrics",
                    "timestamp": time.time(),
                    **fast_data,
                    "alerts": alerts,
                }
                await self.manager.broadcast(message)

                # Calculate sleep time
                elapsed = time.time() - start
                interval = max(self.manager.min_interval, config.MIN_FAST_INTERVAL)
                sleep_time = max(0.05, interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fast loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _slow_loop(self) -> None:
        """
        Slow collection loop with tiered scheduling via tick counter.
        Base interval is ~5s. Different collectors run at different multiples:
          - processes:   every tick     (~5s)
          - temperature: every 2 ticks (~10s)
          - docker:      every 3 ticks (~15s)
          - disk_usage:  every 6 ticks (~30s)
          - services:    every 12 ticks (~60s)
        """
        tick = 0
        while self._running:
            try:
                # Sleep if no clients
                if self.manager.is_sleeping:
                    logger.debug("Slow loop sleeping...")
                    await self.manager.wait_for_wake()
                    logger.debug("Slow loop waking up")
                    tick = 0  # Reset so first wake does a full collection
                    await asyncio.sleep(1)

                start = time.time()
                loop = asyncio.get_event_loop()

                # --- Tiered collection ---
                # Processes: every tick (~5s)
                procs = await loop.run_in_executor(None, collect_processes)

                # Temperature: every 2 ticks (~10s)
                temps = await loop.run_in_executor(None, collect_temperature) if tick % 2 == 0 else None

                # Docker: every 3 ticks (~15s)
                docker = await loop.run_in_executor(None, collect_docker) if tick % 3 == 0 else None

                # Disk usage: every 6 ticks (~30s)
                disks = await loop.run_in_executor(None, collect_disk_usage) if tick % 6 == 0 else None

                # Services: every 12 ticks (~60s)
                services = await loop.run_in_executor(None, collect_services) if tick % 12 == 0 else None

                # Build payload — only include fields that were collected this tick
                slow_data = {"processes": procs}
                if temps is not None:
                    slow_data["temperatures"] = temps
                if docker is not None:
                    slow_data["docker"] = docker
                if disks is not None:
                    slow_data["disks"] = disks
                if services is not None:
                    slow_data["services"] = services

                # Store in ring buffer
                self.store.slow_metrics.append(slow_data)

                # Check disk alerts (only when disks were collected)
                disk_alerts = []
                if disks:
                    for disk in disks:
                        if disk["percent"] >= config.ALERT_DISK_PERCENT:
                            disk_alerts.append({
                                "type": "disk",
                                "mount": disk["mount"],
                                "percent": disk["percent"],
                            })

                # Broadcast
                message = {
                    "type": "slow_metrics",
                    "timestamp": time.time(),
                    **slow_data,
                    "disk_alerts": disk_alerts,
                }
                await self.manager.broadcast(message)

                # Profiling log
                elapsed = time.time() - start
                collected = [k for k in slow_data if k != "processes"]
                logger.debug(
                    f"[slow_loop] tick={tick} elapsed={elapsed*1000:.0f}ms "
                    f"extras={collected or 'processes_only'}"
                )

                # Calculate sleep time
                elapsed = time.time() - start
                interval = max(self.manager.min_interval, config.MIN_SLOW_INTERVAL)
                sleep_time = max(0.5, interval - elapsed)
                await asyncio.sleep(sleep_time)

                tick += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Slow loop error: {e}", exc_info=True)
                await asyncio.sleep(3)


def _check_alerts(data: dict) -> list[dict]:
    """Check fast metrics against alert thresholds."""
    alerts = []

    # CPU alert
    cpu_total = data.get("cpu", {}).get("total", 0)
    if cpu_total >= config.ALERT_CPU_PERCENT:
        alerts.append({"type": "cpu", "value": cpu_total, "threshold": config.ALERT_CPU_PERCENT})

    # Memory alert
    mem_percent = data.get("memory", {}).get("percent", 0)
    if mem_percent >= config.ALERT_MEMORY_PERCENT:
        alerts.append({"type": "memory", "value": mem_percent, "threshold": config.ALERT_MEMORY_PERCENT})

    # Swap alert
    swap_percent = data.get("swap", {}).get("percent", 0)
    if swap_percent >= config.ALERT_SWAP_PERCENT:
        alerts.append({"type": "swap", "value": swap_percent, "threshold": config.ALERT_SWAP_PERCENT})

    return alerts
