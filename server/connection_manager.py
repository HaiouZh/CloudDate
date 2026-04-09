"""
CloudDate — Connection Manager
Manages WebSocket connections and implements the sleep/wake mechanism.
When no clients are connected, the system enters sleep mode to save resources.
"""

import asyncio
import logging
import time
from fastapi import WebSocket

logger = logging.getLogger("clouddate.connections")


class ConnectionManager:
    """
    Manages active WebSocket connections and coordinates sleep/wake behavior.

    Sleep mechanism:
    - When connection count drops to 0, start a sleep timer
    - After SLEEP_DELAY seconds with no new connections, signal sleep
    - When a new connection arrives, signal wake immediately
    """

    def __init__(self, sleep_delay: float = 30.0):
        self._connections: dict[str, WebSocket] = {}
        self._intervals: dict[str, float] = {}  # per-client interval
        self._paused: dict[str, bool] = {}
        self._sleep_delay = sleep_delay
        self._is_sleeping = True  # Start in sleep mode
        self._sleep_timer_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._conn_counter = 0

    @property
    def is_sleeping(self) -> bool:
        return self._is_sleeping

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def min_interval(self) -> float:
        """Get the minimum requested interval across all active clients."""
        if not self._intervals:
            return 2.0
        return min(self._intervals.values())

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection and return its ID."""
        await websocket.accept()

        async with self._lock:
            self._conn_counter += 1
            conn_id = f"ws_{self._conn_counter}_{int(time.time())}"
            self._connections[conn_id] = websocket
            self._intervals[conn_id] = 2.0  # Default interval
            self._paused[conn_id] = False

            logger.info(f"Client connected: {conn_id} (total: {len(self._connections)})")

            # Cancel any pending sleep timer
            if self._sleep_timer_task and not self._sleep_timer_task.done():
                self._sleep_timer_task.cancel()
                self._sleep_timer_task = None

            # Wake up if sleeping
            if self._is_sleeping:
                self._is_sleeping = False
                self._wake_event.set()
                logger.info("System waking up — client connected")

        return conn_id

    async def disconnect(self, conn_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.pop(conn_id, None)
            self._intervals.pop(conn_id, None)
            self._paused.pop(conn_id, None)

            logger.info(f"Client disconnected: {conn_id} (remaining: {len(self._connections)})")

            # If no more connections, start sleep timer
            if len(self._connections) == 0:
                self._start_sleep_timer()

    def _start_sleep_timer(self) -> None:
        """Start the countdown to sleep mode."""
        if self._sleep_timer_task and not self._sleep_timer_task.done():
            self._sleep_timer_task.cancel()

        self._sleep_timer_task = asyncio.create_task(self._sleep_countdown())

    async def _sleep_countdown(self) -> None:
        """Wait for sleep_delay, then enter sleep mode if still no connections."""
        try:
            await asyncio.sleep(self._sleep_delay)
            async with self._lock:
                if len(self._connections) == 0:
                    self._is_sleeping = True
                    self._wake_event.clear()
                    logger.info(f"System entering sleep mode (no connections for {self._sleep_delay}s)")
        except asyncio.CancelledError:
            pass

    async def wait_for_wake(self) -> None:
        """Block until the system is woken up by a client connection."""
        await self._wake_event.wait()

    def set_interval(self, conn_id: str, interval: float) -> None:
        """Set the refresh interval for a specific client."""
        if conn_id in self._intervals:
            self._intervals[conn_id] = interval

    def set_paused(self, conn_id: str, paused: bool) -> None:
        """Set the paused state for a specific client."""
        if conn_id in self._paused:
            self._paused[conn_id] = paused

    def is_paused(self, conn_id: str) -> bool:
        """Check if a client is paused."""
        return self._paused.get(conn_id, False)

    async def broadcast(self, message: dict, conn_ids: list[str] | None = None) -> None:
        """Send a message to specified clients, or all non-paused clients."""
        targets = conn_ids or list(self._connections.keys())
        disconnected = []

        for conn_id in targets:
            if self._paused.get(conn_id, False):
                continue
            ws = self._connections.get(conn_id)
            if ws is None:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(conn_id)

        # Clean up broken connections
        for conn_id in disconnected:
            await self.disconnect(conn_id)

    async def send_to(self, conn_id: str, message: dict) -> bool:
        """Send a message to a specific client. Returns False if failed."""
        ws = self._connections.get(conn_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            await self.disconnect(conn_id)
            return False
