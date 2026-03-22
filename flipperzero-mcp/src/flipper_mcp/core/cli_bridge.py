"""CLI Bridge for Flipper Zero — clean RPC<->CLI mode switching.

The Flipper Zero USB CDC port can operate in two mutually exclusive modes:

1. **CLI mode** — text-based command line interface (the default after USB connect).
   Commands like ``gpio set``, ``led set``, ``ir tx`` are only available here.

2. **RPC mode** — nanopb-delimited protobuf framing initiated by sending
   ``start_rpc_session\\r`` from CLI mode.  All protobuf-based operations
   (storage, app_start, ping, device_info, etc.) require this mode.

CLIBridge manages the transitions between these modes so that callers can
execute CLI commands (``run_cli``) without permanently leaving RPC mode.
"""

import asyncio
import re
import sys
import time
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .protobuf_rpc import ProtobufRPC
    from .transport.base import FlipperTransport


class SessionMode(str, Enum):
    """Current mode of the Flipper USB CDC session."""
    RPC_READY = "RPC_READY"
    SWITCHING_TO_CLI = "SWITCHING_TO_CLI"
    CLI_READY = "CLI_READY"
    SWITCHING_TO_RPC = "SWITCHING_TO_RPC"
    RECOVERING = "RECOVERING"
    DISCONNECTED = "DISCONNECTED"


class CLICommandError(Exception):
    """Raised when the Flipper CLI returns an error response."""

    def __init__(self, message: str, raw_output: str = ""):
        super().__init__(message)
        self.raw_output = raw_output


# Error pattern from Flipper CLI (matches e.g. "gpio error: invalid pin name")
_CLI_ERROR_PATTERN = re.compile(r'\w+\s+error:\s+.*', re.IGNORECASE)
_CLI_PROMPT = ">:"


class CLIBridge:
    """Manages RPC<->CLI mode transitions for hardware commands.

    Usage::

        bridge = CLIBridge(transport, protobuf_rpc, lock)
        result = await bridge.run_cli("gpio set PC3 1")
    """

    def __init__(
        self,
        transport: 'FlipperTransport',
        protobuf_rpc: 'ProtobufRPC',
        lock: asyncio.Lock,
    ):
        self.transport = transport
        self.protobuf_rpc = protobuf_rpc
        self._lock = lock
        self._mode = SessionMode.RPC_READY
        self._log = lambda msg: print(f"[CLIBridge] {msg}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> SessionMode:
        """Current session mode."""
        return self._mode

    async def run_cli(self, command: str, timeout: float = 5.0) -> str:
        """Execute a CLI command, switching out of RPC mode and back.

        Args:
            command: Raw CLI command (e.g. ``"gpio set PC3 1"``).
            timeout: Per-phase timeout in seconds.

        Returns:
            Cleaned CLI response text (prompt and echo stripped).

        Raises:
            CLICommandError: If the Flipper CLI reports an error.
            asyncio.TimeoutError: If the lock cannot be acquired or
                the command times out.
            RuntimeError: If the mode switch fails unrecoverably.
            ValueError: If the command is empty/invalid after sanitization.
        """
        # Acquire the shared lock with a bounded wait to avoid deadlock.
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                "CLIBridge: timed out waiting for transport lock"
            )

        try:
            # 1. Leave RPC mode -> CLI mode
            await self._exit_rpc_mode()

            # 2. Sanitize input
            from .sanitize import sanitize_cli_input
            sanitized = sanitize_cli_input(command)

            # 3. Send command (CR-terminated; the CLI echoes the command back)
            await self.transport.send((sanitized + "\r").encode("ascii"))

            # 4. Read until we see the next prompt
            response = await self._read_until_prompt(timeout)

            return response
        finally:
            # 5. Always attempt to re-enter RPC mode before releasing the lock
            try:
                await self._enter_rpc_mode()
            except Exception as exc:
                self._log(f"WARNING: failed to re-enter RPC mode: {exc}")
                # Mode is RECOVERING; caller should be aware
            self._lock.release()

    # ------------------------------------------------------------------
    # Mode switching internals
    # ------------------------------------------------------------------

    async def _exit_rpc_mode(self) -> None:
        """Transition from RPC mode to CLI mode.

        Strategy:
        1. Send protobuf ``StopSession`` (the clean way).
        2. If that fails, send Ctrl-C + CR as a fallback to break the session.
        3. Drain residual bytes and look for the ``>:`` CLI prompt.
        """
        self._mode = SessionMode.SWITCHING_TO_CLI

        # --- Try clean StopSession first ---
        stop_ok = False
        try:
            stop_ok = await self.protobuf_rpc.stop_rpc_session()
        except Exception as exc:
            self._log(f"StopSession protobuf failed: {exc}")

        if not stop_ok:
            # Fallback: Ctrl-C + CR to break out of any mode
            self._log("StopSession failed; sending Ctrl-C fallback")
            try:
                await self.transport.send(b"\x03\r")
            except Exception as exc:
                self._log(f"Ctrl-C fallback send failed: {exc}")

        # --- Adaptive drain: read until idle ---
        drained = await self._adaptive_drain(max_seconds=0.6)

        # Check for CLI prompt in drained data
        drained_text = drained.decode("ascii", errors="ignore")
        if _CLI_PROMPT in drained_text:
            self._mode = SessionMode.CLI_READY
            return

        # If no prompt yet, send a bare CR to elicit one
        try:
            await self.transport.send(b"\r")
        except Exception:
            pass

        extra = await self._adaptive_drain(max_seconds=0.4)
        extra_text = extra.decode("ascii", errors="ignore")
        if _CLI_PROMPT in extra_text:
            self._mode = SessionMode.CLI_READY
            return

        # Could not confirm CLI prompt
        self._mode = SessionMode.RECOVERING
        raise RuntimeError(
            "CLIBridge: failed to reach CLI prompt after exiting RPC mode"
        )

    async def _enter_rpc_mode(self) -> None:
        """Transition from CLI mode back to RPC mode.

        Sends ``start_rpc_session\\r`` (CR only, NOT CRLF — a trailing LF
        would be consumed as the first byte of the varint length prefix and
        cause ERROR_DECODE + session close on the device).

        Verifies the switch by sending a protobuf ping.  Retries up to 3 times.
        """
        self._mode = SessionMode.SWITCHING_TO_RPC
        last_exc: Optional[Exception] = None

        for attempt in range(3):
            try:
                # Cancel any partially-typed CLI input
                await self.transport.send(b"\x03\r")
                # Small pause for the device to process Ctrl-C
                await asyncio.sleep(0.05)

                # Send the magic command (CR only!)
                await self.transport.send(b"start_rpc_session\r")

                # Drain the CLI echo / banner that comes back
                await self._adaptive_drain(max_seconds=0.4)

                # Clear transport buffer so the ping response is clean
                try:
                    self.transport.clear_receive_buffer()
                except Exception:
                    pass

                # Brief pause to let the device finish switching modes
                await asyncio.sleep(0.2)

                # Verify with a protobuf ping
                echoed = await self.protobuf_rpc.ping(data=b"cli_bridge")
                if echoed == b"cli_bridge":
                    self.protobuf_rpc._rpc_session_started = True
                    self._mode = SessionMode.RPC_READY
                    return

                self._log(
                    f"RPC ping verification failed on attempt {attempt + 1} "
                    f"(got {echoed!r})"
                )
            except Exception as exc:
                last_exc = exc
                self._log(f"enter_rpc attempt {attempt + 1} failed: {exc}")

            # Small backoff before retry
            await asyncio.sleep(0.1 * (attempt + 1))

        self._mode = SessionMode.RECOVERING
        raise RuntimeError(
            f"CLIBridge: failed to re-enter RPC mode after 3 attempts"
            f"{f': {last_exc}' if last_exc else ''}"
        )

    # ------------------------------------------------------------------
    # Reading / draining helpers
    # ------------------------------------------------------------------

    async def _read_until_prompt(self, timeout: float) -> str:
        """Read CLI output until the ``>:`` prompt appears.

        Returns the response text with the echoed command (first line)
        and the trailing prompt stripped.

        Raises:
            CLICommandError: If the output matches the Flipper error pattern.
            asyncio.TimeoutError: If the prompt is not seen within *timeout*.
        """
        buf = bytearray()

        async def _reader() -> str:
            while True:
                try:
                    chunk = await self.transport.receive(timeout=0.1)
                except Exception:
                    chunk = b""
                if chunk:
                    buf.extend(chunk)
                    text = buf.decode("ascii", errors="ignore")
                    if _CLI_PROMPT in text:
                        return text
                # Yield to event loop even on empty reads
                await asyncio.sleep(0)

        raw_text = await asyncio.wait_for(_reader(), timeout=timeout)

        # Split into lines for processing
        lines = raw_text.split("\r\n")
        # Fall back to splitting on plain \r or \n if the device uses those
        if len(lines) == 1:
            lines = raw_text.replace("\r", "\n").split("\n")

        # Strip the first line (command echo) and trailing prompt
        if lines:
            lines = lines[1:]  # drop echo
        # Remove any lines that are just the prompt or empty
        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped == _CLI_PROMPT or stripped == ">:" or not stripped:
                continue
            # Strip trailing prompt from last content line
            if stripped.endswith(_CLI_PROMPT):
                stripped = stripped[: -len(_CLI_PROMPT)].rstrip()
                if stripped:
                    cleaned.append(stripped)
                continue
            cleaned.append(stripped)

        result = "\n".join(cleaned).strip()

        # Check for error pattern
        err_match = _CLI_ERROR_PATTERN.search(result)
        if err_match:
            raise CLICommandError(err_match.group(0), raw_output=result)

        return result

    async def _adaptive_drain(self, max_seconds: float = 0.6) -> bytes:
        """Drain pending bytes from the transport with adaptive timing.

        Reads with short (50 ms) timeouts in a loop.  Stops when either:
        - no data is received on a read, or
        - *max_seconds* wall time has elapsed.

        Returns all bytes accumulated during the drain.
        """
        accumulated = bytearray()
        end = time.monotonic() + max_seconds

        while time.monotonic() < end:
            try:
                chunk = await self.transport.receive(timeout=0.05)
            except Exception:
                chunk = b""
            if chunk:
                accumulated.extend(chunk)
            else:
                # No data on this read — if we already have some data,
                # the device is likely done sending.  If not, keep waiting
                # until the deadline in case data is still arriving.
                if accumulated:
                    break

        return bytes(accumulated)
