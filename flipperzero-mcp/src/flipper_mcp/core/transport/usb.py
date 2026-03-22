"""USB Serial transport for Flipper Zero."""

import asyncio
import sys
import time
from typing import Optional
import serial
import serial.tools.list_ports

from .base import FlipperTransport

# Flipper Zero USB VID:PID
FLIPPER_VID = 0x0483  # STMicroelectronics
FLIPPER_PID = 0x5740  # Virtual COM Port

# Baud rates to try during auto-detection, ordered by likelihood
BAUD_CANDIDATES = [230400, 115200, 460800, 921600]

# Retry configuration for connect()
CONNECT_MAX_RETRIES = 3
CONNECT_RETRY_DELAYS = [1.0, 1.5, 2.0]

# Process-wide lock: only one USBTransport connection at a time.
# Prevents two scripts/sessions from fighting over the serial port.
_port_lock: dict[str, "USBTransport"] = {}


class USBTransport(FlipperTransport):
    """
    USB Serial transport implementation.

    Connects to Flipper Zero via USB serial port.
    Enforces single-connection-per-port at the process level.
    """
    
    def __init__(self, config: dict):
        """
        Initialize USB transport.

        Args:
            config: USB configuration with 'port' and 'baudrate'.
                    Set baudrate to "auto" (or omit) to auto-detect.
        """
        super().__init__(config)
        # IMPORTANT: dict.get(default=...) eagerly evaluates the default, which would
        # auto-detect even when an explicit port was provided. Keep this lazy.
        configured_port = config.get("port")
        self.port = configured_port if configured_port else self._auto_detect_port()
        self.baudrate = config.get("baudrate", "auto")
        self.timeout = config.get("timeout", 1.0)
        self.serial: Optional[serial.Serial] = None
        self._last_activity: float = 0.0
    
    def _auto_detect_port(self) -> str:
        """
        Auto-detect Flipper Zero USB port.
        
        Supports both macOS (tty.usbmodem*) and Linux (ttyACM*, ttyUSB*).
        
        Returns:
            Port path or default
        """
        import platform
        system = platform.system()
        
        # Look for Flipper Zero USB device
        ports = serial.tools.list_ports.comports()
        detected_ports = []
        
        for port in ports:
            device = port.device
            is_flipper = False
            
            # Flipper Zero VID:PID match (most reliable)
            if port.vid == FLIPPER_VID and port.pid == FLIPPER_PID:
                is_flipper = True
            # Description match
            elif "Flipper" in str(port.description):
                is_flipper = True
            # macOS-specific: check for usbmodem pattern with "flip" in name
            elif system == "Darwin" and "usbmodem" in device.lower() and "flip" in device.lower():
                is_flipper = True
            
            if is_flipper:
                # On macOS, prefer cu.* for initiating outgoing serial connections.
                # (tty.* is typically for incoming/call-in.)
                if system == "Darwin":
                    if device.startswith("/dev/tty."):
                        # Prefer cu.* version if available
                        cu_device = device.replace("/dev/tty.", "/dev/cu.")
                        import os
                        if os.path.exists(cu_device):
                            device = cu_device
                
                detected_ports.append((device, port))
        
        # Return the first detected port
        if detected_ports:
            device, port = detected_ports[0]
            print(f"   Detected Flipper Zero at {device}", file=sys.stderr)
            return device
        
        # Platform-specific fallback
        if system == "Darwin":
            # macOS: try common usbmodem pattern
            fallback = "/dev/tty.usbmodemflip_1"
            print(f"   ⚠️  No Flipper Zero detected, using fallback: {fallback}", file=sys.stderr)
            return fallback
        else:
            # Linux: try common ACM port
            fallback = "/dev/ttyACM0"
            print(f"   ⚠️  No Flipper Zero detected, using fallback: {fallback}", file=sys.stderr)
            return fallback
    
    async def connect(self) -> bool:
        """
        Connect to Flipper Zero via USB.

        When baudrate is "auto" (or not set), tries each candidate baud rate
        by opening the port, sending a probe byte, and checking for a response.
        If an explicit numeric baud rate is configured, uses it directly.

        The entire connect attempt is wrapped in a retry loop with exponential
        backoff (up to CONNECT_MAX_RETRIES attempts).

        Returns:
            True if connection successful
        """
        # Enforce single connection per port
        if self.port in _port_lock and _port_lock[self.port] is not self:
            other = _port_lock[self.port]
            if other.connected:
                raise RuntimeError(
                    f"Port {self.port} is already in use by another connection. "
                    "Close the existing connection first."
                )
            # Stale entry — clean up
            del _port_lock[self.port]

        for attempt in range(CONNECT_MAX_RETRIES):
            try:
                success = await self._try_connect()
                if success:
                    self.connected = True
                    _port_lock[self.port] = self
                    self.mark_activity()
                    return True
            except (serial.SerialException, OSError) as e:
                # Ensure any partially-opened port is closed before retry
                self._close_serial_safe()
                if attempt < CONNECT_MAX_RETRIES - 1:
                    delay = CONNECT_RETRY_DELAYS[attempt]
                    print(
                        f"USB connect attempt {attempt + 1}/{CONNECT_MAX_RETRIES} "
                        f"failed: {e}  — retrying in {delay}s",
                        file=sys.stderr,
                    )
                    await asyncio.sleep(delay)
                else:
                    print(
                        f"USB connection failed after {CONNECT_MAX_RETRIES} attempts: {e}",
                        file=sys.stderr,
                    )

        self.connected = False
        return False

    async def _try_connect(self) -> bool:
        """
        Single connection attempt.  Handles baud auto-detection when configured.

        Returns:
            True if connection established and (optionally) probe succeeded.
        """
        if self.baudrate == "auto" or self.baudrate is None:
            return await self._connect_auto_baud()
        else:
            return await self._connect_fixed_baud(int(self.baudrate))

    async def _connect_auto_baud(self) -> bool:
        """
        Try each candidate baud rate, probing for a response.

        On success, sets ``self.baudrate`` to the working rate and leaves
        ``self.serial`` open.

        Returns:
            True if a working baud rate was found.
        """
        loop = asyncio.get_event_loop()
        for candidate in BAUD_CANDIDATES:
            try:
                probe_serial = serial.Serial(
                    port=self.port,
                    baudrate=candidate,
                    timeout=0.3,
                )
            except (serial.SerialException, OSError):
                # Port doesn't exist or is busy — no point trying other rates
                # on this attempt; let the outer retry loop handle it.
                raise

            try:
                # Send a bare carriage-return as a lightweight probe.
                # The Flipper CLI echoes a prompt in response.
                await loop.run_in_executor(None, probe_serial.write, b"\r")
                response = await loop.run_in_executor(None, probe_serial.read, 64)
                if response:
                    # Got a response — this baud rate works.
                    self.baudrate = candidate
                    self.serial = probe_serial
                    print(
                        f"   Baud auto-detect: {candidate} works",
                        file=sys.stderr,
                    )
                    # Let the connection stabilize after probe
                    await asyncio.sleep(0.3)
                    return True
            except (serial.SerialException, OSError):
                pass

            # No response or error at this rate — close and try next
            try:
                probe_serial.close()
            except Exception:
                pass

        print("   Baud auto-detect: no candidate responded", file=sys.stderr)
        return False

    async def _connect_fixed_baud(self, baudrate: int) -> bool:
        """
        Open the serial port at a fixed baud rate (no probing).

        Returns:
            True if the port was opened successfully.
        """
        self.serial = serial.Serial(
            port=self.port,
            baudrate=baudrate,
            timeout=self.timeout,
        )
        # Wait for connection to stabilize
        await asyncio.sleep(0.5)
        return True

    def _close_serial_safe(self) -> None:
        """Close self.serial if open, swallowing errors."""
        if self.serial:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
            self.serial = None
    
    async def disconnect(self) -> None:
        """Close USB connection and release port lock."""
        self._close_serial_safe()
        self.connected = False
        if self.port in _port_lock and _port_lock[self.port] is self:
            del _port_lock[self.port]

    def mark_activity(self) -> None:
        """Record the current time as the last transport activity.

        Called automatically by ``send()`` and ``receive()``.  Also available
        for external callers (e.g. the keepalive manager) to update after an
        out-of-band health probe.
        """
        self._last_activity = time.monotonic()

    async def send(self, data: bytes) -> None:
        """
        Send data over USB.

        Args:
            data: Bytes to send
        """
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("USB not connected")

        # Run serial write in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.serial.write, data)
        self.mark_activity()

    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """
        Receive data from USB.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Received bytes
        """
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("USB not connected")

        # Only set timeout when it differs from current to avoid
        # a termios/ioctl syscall on every read (hot path in drain loops).
        old_timeout = self.serial.timeout
        needs_restore = timeout is not None and timeout != old_timeout
        if needs_restore:
            self.serial.timeout = timeout

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self.serial.read,
                4096
            )
            if data:
                self.mark_activity()
            return data
        finally:
            if needs_restore:
                self.serial.timeout = old_timeout
    
    async def is_connected(self) -> bool:
        """
        Check if USB is connected.
        
        Returns:
            True if connected
        """
        return self.connected and self.serial is not None and self.serial.is_open
