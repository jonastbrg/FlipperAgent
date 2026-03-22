"""ESP32 Marauder WiFi module for Flipper Zero MCP.

Three modes of operation (auto-selected):

1. **UART Bridge** (preferred): Launch the UART Bridge .fap on the Flipper.
   It switches to dual-CDC USB — a second serial port appears. Set
   MARAUDER_PORT to that port (e.g., /dev/cu.usbmodemflip_*3).
   Commands go: pyserial → USB CDC ch1 → Flipper → GPIO UART → ESP32.
   Fully autonomous — no manual Flipper interaction needed.

2. **Direct serial**: If the ESP32 has its own USB connection, set
   MARAUDER_PORT to its port. Commands go directly to the ESP32.

3. **Script mode** (fallback): Writes JSON scripts to the Flipper SD card
   at /ext/apps_data/marauder/scripts/. User runs them from the Marauder
   companion app manually. Results saved to SD for later retrieval.

When MARAUDER_PORT is set, modes 1/2 are used (direct serial commands).
When unset, mode 3 is used (SD card scripts).
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from mcp.types import Tool, TextContent

from ..base_module import FlipperModule
from ...core.risk import RiskLevel


# Path on Flipper SD card for Marauder scripts
SCRIPTS_PATH = "/ext/apps_data/marauder/scripts"
PCAP_PATH = "/ext/apps_data/marauder"
LOG_PATH = "/ext/apps_data/marauder"


class MarauderModule(FlipperModule):
    """ESP32 Marauder WiFi operations via Flipper companion app scripts."""

    def __init__(self, flipper_client: Any):
        super().__init__(flipper_client)
        self._serial = None
        self._port = os.environ.get("MARAUDER_PORT")

    @property
    def name(self) -> str:
        return "marauder"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "ESP32 Marauder WiFi: scan, sniff, deauth, evil portal, PMKID capture"

    def get_risk_levels(self) -> Dict[str, RiskLevel]:
        return {
            "marauder_scan_ap": RiskLevel.MEDIUM,
            "marauder_scan_sta": RiskLevel.MEDIUM,
            "marauder_sniff_pmkid": RiskLevel.MEDIUM,
            "marauder_sniff_raw": RiskLevel.MEDIUM,
            "marauder_sniff_beacon": RiskLevel.MEDIUM,
            "marauder_sniff_deauth": RiskLevel.MEDIUM,
            "marauder_deauth": RiskLevel.HIGH,
            "marauder_beacon_spam": RiskLevel.HIGH,
            "marauder_probe_flood": RiskLevel.HIGH,
            "marauder_script": RiskLevel.MEDIUM,
            "marauder_exec": RiskLevel.HIGH,
            "marauder_list_scripts": RiskLevel.LOW,
            "marauder_list_pcaps": RiskLevel.LOW,
            "marauder_read_log": RiskLevel.LOW,
        }

    def get_tools(self) -> List[Tool]:
        return [
            # --- Script generation (write to SD, run from Flipper UI) ---
            Tool(
                name="marauder_scan_ap",
                description=(
                    "Create a WiFi AP scan script on the Flipper SD card. "
                    "Run it from the Marauder companion app: Scripts → select → Run."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 15,
                            "description": "Scan duration in seconds (default: 15)",
                        },
                        "channel": {
                            "type": "integer",
                            "description": "WiFi channel 1-14 (omit for all channels)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_scan_sta",
                description=(
                    "Create a WiFi station (client) scan script. "
                    "Discovers connected devices and their associated APs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 15,
                            "description": "Scan duration in seconds (default: 15)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_sniff_pmkid",
                description=(
                    "Create a PMKID capture script. Captures WPA2 handshakes for offline cracking. "
                    "Saves PCAP to Flipper SD card."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 60,
                            "description": "Capture duration in seconds (default: 60)",
                        },
                        "channel": {
                            "type": "integer",
                            "description": "WiFi channel (omit for all)",
                        },
                        "force_deauth": {
                            "type": "boolean",
                            "default": True,
                            "description": "Send deauth to force handshake (default: true)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_sniff_raw",
                description="Create a raw packet capture script. Saves PCAP to SD for Wireshark analysis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "Capture duration in seconds (default: 30)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_sniff_beacon",
                description="Create a beacon frame sniff script. Captures AP advertisements.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "Sniff duration in seconds (default: 30)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_sniff_deauth",
                description="Create a deauth frame sniff script. Detects active WiFi attacks in the area.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "Sniff duration in seconds (default: 30)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_deauth",
                description=(
                    "Create a deauthentication attack script. Disconnects clients from a WiFi AP. "
                    "WARNING: Disrupts WiFi connectivity. Authorized targets only. "
                    "Run scan_ap first, then select target in companion app before running."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 10,
                            "description": "Attack duration in seconds (default: 10)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_beacon_spam",
                description=(
                    "Create a beacon spam script. Floods fake WiFi SSIDs. "
                    "WARNING: Disrupts WiFi scanning for all nearby devices."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ssids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of SSID names to broadcast",
                        },
                        "random_count": {
                            "type": "integer",
                            "default": 0,
                            "description": "Number of random SSIDs to generate (in addition to named ones)",
                        },
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "Duration in seconds (default: 30)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_probe_flood",
                description="Create a probe request flood script. Tests AP resilience.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "integer",
                            "default": 10,
                            "description": "Duration in seconds (default: 10)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="marauder_script",
                description=(
                    "Create a custom multi-stage Marauder script (JSON format). "
                    "Stages run in order: scan → select → attack/sniff. "
                    "Saved to Flipper SD card for execution via companion app."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Script name (without extension)",
                        },
                        "description": {
                            "type": "string",
                            "default": "",
                            "description": "Script description",
                        },
                        "stages": {
                            "type": "array",
                            "description": (
                                "Array of stage objects. Each object has one key (the stage type) "
                                "with config as value. Types: scan, select, deauth, probe, "
                                "sniffRaw, sniffBeacon, sniffDeauth, sniffPmkid, sniffPwn, "
                                "beaconList, beaconAp, exec, delay"
                            ),
                            "items": {"type": "object"},
                        },
                        "save_pcap": {
                            "type": "boolean",
                            "default": True,
                            "description": "Save PCAP captures to SD (default: true)",
                        },
                        "repeat": {
                            "type": "integer",
                            "default": 1,
                            "description": "Times to repeat the script (default: 1)",
                        },
                    },
                    "required": ["name", "stages"],
                },
            ),
            Tool(
                name="marauder_exec",
                description=(
                    "Create a script that executes a raw Marauder command. "
                    "Use for commands not covered by other tools (e.g., 'wardrive', 'karma -p', 'info'). "
                    "WARNING: No input validation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Raw Marauder command (e.g., 'wardrive', 'karma -p')",
                        },
                    },
                    "required": ["command"],
                },
            ),
            # --- Read results from SD ---
            Tool(
                name="marauder_list_scripts",
                description="List Marauder scripts saved on the Flipper SD card.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="marauder_list_pcaps",
                description="List PCAP capture files saved by Marauder on the Flipper SD card.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="marauder_read_log",
                description="Read the Marauder log file from the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lines": {
                            "type": "integer",
                            "default": 100,
                            "description": "Number of lines to read (default: 100, from end)",
                        },
                    },
                    "required": [],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        handlers = {
            "marauder_scan_ap": self._scan_ap,
            "marauder_scan_sta": self._scan_sta,
            "marauder_sniff_pmkid": self._sniff_pmkid,
            "marauder_sniff_raw": self._sniff_raw,
            "marauder_sniff_beacon": self._sniff_beacon,
            "marauder_sniff_deauth": self._sniff_deauth,
            "marauder_deauth": self._deauth,
            "marauder_beacon_spam": self._beacon_spam,
            "marauder_probe_flood": self._probe_flood,
            "marauder_script": self._custom_script,
            "marauder_exec": self._exec,
            "marauder_list_scripts": self._list_scripts,
            "marauder_list_pcaps": self._list_pcaps,
            "marauder_read_log": self._read_log,
        }
        return await self._dispatch(tool_name, arguments, handlers, "Marauder")

    # --- Direct serial (UART Bridge / direct USB) ---

    def _has_serial(self) -> bool:
        """Check if direct serial mode is available."""
        return self._port is not None

    async def _serial_cmd(self, command: str, duration: float = 5.0,
                          stop_after: bool = False) -> str:
        """Send a command via direct serial and collect output."""
        import serial as pyserial
        import asyncio

        if self._serial is None or not self._serial.is_open:
            self._serial = pyserial.Serial(self._port, 115200, timeout=1)
            await asyncio.sleep(0.5)
            self._serial.reset_input_buffer()

        self._serial.reset_input_buffer()
        self._serial.write(f"{command}\n".encode())
        self._serial.flush()

        lines = []
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if self._serial.in_waiting:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)
            else:
                await asyncio.sleep(0.1)

        if stop_after:
            self._serial.write(b"stopscan\n")
            self._serial.flush()
            await asyncio.sleep(1)
            while self._serial.in_waiting:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)

        return "\n".join(lines)

    # --- Script writing helpers (fallback for SD card mode) ---

    async def _write_script(self, name: str, script: dict) -> str:
        """Write a JSON script to the Flipper SD card. Returns the file path."""
        # Ensure scripts directory exists
        try:
            await self.flipper.run_cli(f"storage mkdir {SCRIPTS_PATH}", timeout=3)
        except Exception:
            pass  # Directory may already exist

        path = f"{SCRIPTS_PATH}/{name}.json"
        content = json.dumps(script, indent=2)
        await self.flipper.run_cli(
            f'storage write {path} {content}', timeout=5
        )
        return path

    def _make_script(self, description: str, stages: list,
                     save_pcap: bool = True, repeat: int = 1) -> dict:
        """Build a Marauder script JSON object."""
        return {
            "meta": {
                "description": description,
                "repeat": repeat,
                "enableLed": True,
                "savePcap": save_pcap,
            },
            "stages": stages,
        }

    # --- Tool implementations (serial when available, SD scripts as fallback) ---

    async def _scan_ap(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 15)
        if self._has_serial():
            output = await self._serial_cmd("scanap", timeout, stop_after=True)
            return [TextContent(type="text", text=f"WiFi AP scan ({timeout}s):\n{output}")]
        # Fallback: SD card script
        stage = {"scan": {"type": "ap", "timeout": timeout}}
        if args.get("channel"):
            stage["scan"]["channel"] = args["channel"]
        name = f"mcp_scan_ap_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"AP scan ({timeout}s)", [stage], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper: Marauder → Scripts → {name}")]

    async def _scan_sta(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 15)
        if self._has_serial():
            output = await self._serial_cmd("scansta", timeout, stop_after=True)
            return [TextContent(type="text", text=f"WiFi station scan ({timeout}s):\n{output}")]
        name = f"mcp_scan_sta_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Station scan", [{"scan": {"type": "station", "timeout": timeout}}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper: Marauder → Scripts → {name}")]

    async def _sniff_pmkid(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 60)
        if self._has_serial():
            channel = args.get("channel")
            if channel:
                await self._serial_cmd(f"channel -s {channel}", 1.0)
            output = await self._serial_cmd("sniffpmkid", timeout, stop_after=True)
            return [TextContent(type="text", text=f"PMKID capture ({timeout}s):\n{output}")]
        stage = {"sniffPmkid": {"timeout": timeout, "forceDeauth": args.get("force_deauth", True)}}
        if args.get("channel"):
            stage["sniffPmkid"]["channel"] = args["channel"]
        name = f"mcp_pmkid_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"PMKID capture", [stage]))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper. PCAP saves to SD.")]

    async def _sniff_raw(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 30)
        if self._has_serial():
            output = await self._serial_cmd("sniffraw", timeout, stop_after=True)
            return [TextContent(type="text", text=f"Raw capture ({timeout}s, PCAP on SD):\n{output}")]
        name = f"mcp_raw_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Raw capture", [{"sniffRaw": {"timeout": timeout}}]))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper. PCAP saves to SD.")]

    async def _sniff_beacon(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 30)
        if self._has_serial():
            output = await self._serial_cmd("sniffbeacon", timeout, stop_after=True)
            return [TextContent(type="text", text=f"Beacon sniff ({timeout}s):\n{output}")]
        name = f"mcp_beacon_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Beacon sniff", [{"sniffBeacon": {"timeout": timeout}}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper.")]

    async def _sniff_deauth(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 30)
        if self._has_serial():
            output = await self._serial_cmd("sniffdeauth", timeout, stop_after=True)
            return [TextContent(type="text", text=f"Deauth detection ({timeout}s):\n{output}")]
        name = f"mcp_sniff_deauth_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Deauth detect", [{"sniffDeauth": {"timeout": timeout}}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper.")]

    async def _deauth(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 10)
        if self._has_serial():
            output = await self._serial_cmd(f"attack -t deauth", timeout, stop_after=True)
            return [TextContent(type="text", text=f"Deauth attack ({timeout}s):\n{output}")]
        stages = [
            {"scan": {"type": "ap", "timeout": 10}},
            {"select": {"type": "ap", "filter": "all"}},
            {"deauth": {"timeout": timeout}},
        ]
        name = f"mcp_deauth_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Deauth", stages, save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Edit select stage to target specific AP.")]

    async def _beacon_spam(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 30)
        mode = args.get("mode", "random")
        if self._has_serial():
            cmd = {"random": "attack -t beacon -r", "rickroll": "attack -t rickroll", "list": "attack -t beacon -a"}.get(mode, "attack -t beacon -r")
            output = await self._serial_cmd(cmd, timeout, stop_after=True)
            return [TextContent(type="text", text=f"Beacon spam ({mode}, {timeout}s):\n{output}")]
        ssids = args.get("ssids", [])
        random_count = args.get("random_count", 20)
        stage_data = {"timeout": timeout}
        if ssids:
            stage_data["ssids"] = ssids
        else:
            stage_data["generate"] = random_count
        name = f"mcp_beacon_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Beacon spam", [{"beaconList": stage_data}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper.")]

    async def _probe_flood(self, args: dict) -> Sequence[TextContent]:
        timeout = args.get("timeout", 10)
        if self._has_serial():
            output = await self._serial_cmd("attack -t probe", timeout, stop_after=True)
            return [TextContent(type="text", text=f"Probe flood ({timeout}s):\n{output}")]
        name = f"mcp_probe_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"Probe flood", [{"probe": {"timeout": timeout}}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Run on Flipper.")]

    async def _custom_script(self, args: dict) -> Sequence[TextContent]:
        name = args["name"]
        stages = args["stages"]
        script = self._make_script(args.get("description", ""), stages, args.get("save_pcap", True), args.get("repeat", 1))
        path = await self._write_script(name, script)
        return [TextContent(type="text", text=f"Script written to {path}. {len(stages)} stages. Run on Flipper.")]

    async def _exec(self, args: dict) -> Sequence[TextContent]:
        command = args["command"]
        if self._has_serial():
            duration = args.get("duration", 10.0)
            output = await self._serial_cmd(command, duration)
            return [TextContent(type="text", text=f"Marauder [{command}]:\n{output}")]
        name = f"mcp_exec_{int(time.time())}"
        path = await self._write_script(name, self._make_script(f"exec: {command}", [{"exec": {"command": command}}], save_pcap=False))
        return [TextContent(type="text", text=f"Script written to {path}. Command: {command}. Run on Flipper.")]

    # --- Read results ---

    async def _list_scripts(self, args: dict) -> Sequence[TextContent]:
        try:
            result = await self.flipper.run_cli(
                f"storage list {SCRIPTS_PATH}", timeout=5
            )
            return [TextContent(type="text", text=f"Marauder scripts on SD:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Failed to list scripts: {e}")]

    async def _list_pcaps(self, args: dict) -> Sequence[TextContent]:
        try:
            result = await self.flipper.run_cli(
                f"storage list {PCAP_PATH}", timeout=5
            )
            # Filter for .pcap files
            lines = result.split("\n") if result else []
            pcaps = [l for l in lines if ".pcap" in l.lower()]
            if pcaps:
                return [TextContent(type="text", text=f"PCAP files:\n" + "\n".join(pcaps))]
            return [TextContent(type="text", text=f"No PCAP files found.\nAll files in {PCAP_PATH}:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Failed to list pcaps: {e}")]

    async def _read_log(self, args: dict) -> Sequence[TextContent]:
        try:
            # Try common log locations
            for log_path in [
                f"{PCAP_PATH}/marauder.log",
                f"{PCAP_PATH}/log.txt",
                f"/ext/apps_data/marauder/logs/marauder.log",
            ]:
                try:
                    result = await self.flipper.run_cli(
                        f"storage read {log_path}", timeout=5
                    )
                    if result and len(result.strip()) > 0:
                        return [TextContent(type="text", text=f"Marauder log ({log_path}):\n{result}")]
                except Exception:
                    continue
            return [TextContent(type="text", text="No Marauder log file found on SD card.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Failed to read log: {e}")]

    async def on_unload(self) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(b"stopscan\n")
                self._serial.close()
            except Exception:
                pass
