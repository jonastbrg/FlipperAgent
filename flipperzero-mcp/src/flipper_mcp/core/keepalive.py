"""Keepalive manager for Flipper Zero connection.

Sends periodic protobuf pings when the transport has been idle for longer
than ``KEEPALIVE_IDLE_THRESHOLD`` seconds.  This prevents the Flipper USB
CDC session from timing out during long gaps between MCP tool calls.

Usage::

    from .keepalive import KeepaliveManager

    mgr = KeepaliveManager(client)
    mgr.start()   # spawns background asyncio task
    ...
    mgr.stop()    # cancels the task
"""

import asyncio
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .flipper_client import FlipperClient

KEEPALIVE_CHECK_INTERVAL = 1.0   # Check every 1s
KEEPALIVE_IDLE_THRESHOLD = 3.5   # Send ping if idle > 3.5s


class KeepaliveManager:
    """Background task that pings the Flipper when the connection goes idle."""

    def __init__(self, client: "FlipperClient"):
        self.client = client
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the keepalive loop as a background asyncio task.

        Safe to call multiple times; a new task is only created if the
        previous one has finished or was never started.
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._keepalive_loop())

    def stop(self) -> None:
        """Cancel the keepalive task if it is running."""
        if self._task and not self._task.done():
            self._task.cancel()

    async def _keepalive_loop(self) -> None:
        """Periodically check idle time and send a protobuf ping if needed."""
        while True:
            try:
                await asyncio.sleep(KEEPALIVE_CHECK_INTERVAL)

                if not self.client.connected:
                    continue

                transport = self.client.transport
                last = getattr(transport, "_last_activity", 0.0)
                if time.monotonic() - last > KEEPALIVE_IDLE_THRESHOLD:
                    # Send protobuf ping to keep the session alive
                    if self.client.rpc and self.client.rpc.protobuf_rpc:
                        try:
                            await self.client.rpc.protobuf_ping()
                            # Update the transport timestamp so we don't
                            # immediately ping again on the next cycle.
                            if hasattr(transport, "mark_activity"):
                                transport.mark_activity()
                        except Exception:
                            # Ping failed — not fatal.  The next health check
                            # or tool call will surface the real error.
                            pass

            except asyncio.CancelledError:
                return
            except Exception:
                # Guard against unexpected errors to keep the loop alive.
                continue
