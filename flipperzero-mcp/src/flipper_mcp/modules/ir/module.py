"""Infrared module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule

# Supported IR protocols (from Flipper firmware)
IR_PROTOCOLS = [
    "NEC", "NEC42", "NEC42ext", "Samsung32", "RC6", "RC5", "RC5X",
    "SIRC", "SIRC15", "SIRC20",
]


class IRModule(FlipperModule):
    """Infrared transmit and receive operations."""

    @property
    def name(self) -> str:
        return "ir"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Infrared: transmit and receive IR signals (NEC, Samsung, RC5/6, SIRC)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="ir_tx",
                description=(
                    "Transmit an IR signal using a known protocol. "
                    f"Supported protocols: {', '.join(IR_PROTOCOLS)}"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "protocol": {
                            "type": "string",
                            "enum": IR_PROTOCOLS,
                            "description": "IR protocol name",
                        },
                        "address": {
                            "type": "string",
                            "description": "Device address in hex (e.g., '04')",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command in hex (e.g., '08')",
                        },
                    },
                    "required": ["protocol", "address", "command"],
                },
            ),
            Tool(
                name="ir_tx_raw",
                description="Transmit a raw IR signal with custom frequency and duty cycle.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "frequency": {
                            "type": "integer",
                            "default": 38000,
                            "description": "Carrier frequency in Hz (default: 38000)",
                        },
                        "duty_cycle": {
                            "type": "number",
                            "default": 0.33,
                            "description": "Duty cycle 0.0-1.0 (default: 0.33)",
                        },
                        "samples": {
                            "type": "string",
                            "description": "Space-separated pulse/gap durations in microseconds",
                        },
                    },
                    "required": ["samples"],
                },
            ),
            Tool(
                name="ir_rx",
                description="Receive/capture an IR signal. Point a remote at the Flipper and press a button.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Capture duration in seconds (default: 5)",
                        }
                    },
                    "required": [],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        handlers = {
            "ir_tx": self._tx,
            "ir_tx_raw": self._tx_raw,
            "ir_rx": self._rx,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _tx(self, args: dict) -> Sequence[TextContent]:
        protocol = args["protocol"]
        address = self._format_hex_bytes(args["address"])
        command = self._format_hex_bytes(args["command"])
        try:
            result = await self.flipper.run_cli(f"ir tx {protocol} {address} {command}")
            return [TextContent(type="text", text=f"IR TX ({protocol}) complete. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"IR TX failed: {e}")]

    async def _tx_raw(self, args: dict) -> Sequence[TextContent]:
        freq = args.get("frequency", 38000)
        dc = args.get("duty_cycle", 0.33)
        samples = args["samples"]
        dc_pct = int(dc * 100)
        try:
            result = await self.flipper.run_cli(
                f"ir tx RAW F:{freq} DC:{dc_pct} {samples}"
            )
            return [TextContent(type="text", text=f"IR raw TX complete. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"IR raw TX failed: {e}")]

    async def _rx(self, args: dict) -> Sequence[TextContent]:
        duration = args.get("duration", 5.0)
        try:
            result = await self.flipper.run_cli("ir rx", timeout=duration + 2)
            return [TextContent(type="text", text=f"IR capture:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"IR RX failed: {e}")]

    @staticmethod
    def _format_hex_bytes(hex_str: str) -> str:
        """Format hex string as space-separated bytes for Flipper CLI.

        '04' -> '04 00 00 00', 'AB12' -> '12 AB 00 00' (little-endian pad to 4 bytes)
        """
        hex_str = hex_str.replace("0x", "").replace(" ", "")
        raw = bytes.fromhex(hex_str.zfill(2 * ((len(hex_str) + 1) // 2)))
        padded = raw[:4].ljust(4, b"\x00")
        return " ".join(f"{b:02X}" for b in padded)
