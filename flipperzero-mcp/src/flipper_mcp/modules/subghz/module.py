"""Sub-GHz radio module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class SubGHzModule(FlipperModule):
    """Sub-GHz radio operations: transmit, receive, decode."""

    @property
    def name(self) -> str:
        return "subghz"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Sub-GHz radio: transmit, receive, and decode RF signals (300-928 MHz)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="subghz_tx",
                description=(
                    "Transmit a Sub-GHz signal. Sends a hex-encoded key at the "
                    "specified frequency. WARNING: RF transmission — verify legal "
                    "compliance for your region."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hex_key": {
                            "type": "string",
                            "description": "Hex-encoded key to transmit (e.g., 'DEADBEEF')",
                        },
                        "frequency": {
                            "type": "integer",
                            "default": 433920000,
                            "description": "Frequency in Hz (default: 433920000)",
                        },
                        "te": {
                            "type": "integer",
                            "default": 403,
                            "description": "Pulse duration in microseconds (default: 403)",
                        },
                        "repeat": {
                            "type": "integer",
                            "default": 10,
                            "description": "Number of transmissions (default: 10)",
                        },
                    },
                    "required": ["hex_key"],
                },
            ),
            Tool(
                name="subghz_tx_from_file",
                description="Transmit a Sub-GHz signal from a .sub file on the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to .sub file on Flipper (e.g., '/ext/subghz/signal.sub')",
                        },
                        "repeat": {
                            "type": "integer",
                            "default": 1,
                            "description": "Number of repeats (default: 1)",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            Tool(
                name="subghz_rx",
                description=(
                    "Receive Sub-GHz signals at a given frequency. "
                    "Listens for the specified duration and returns captured data."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "frequency": {
                            "type": "integer",
                            "default": 433920000,
                            "description": "Frequency in Hz (default: 433920000)",
                        },
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Listen duration in seconds (default: 5)",
                        },
                        "raw": {
                            "type": "boolean",
                            "default": False,
                            "description": "Capture raw signal data (default: false)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="subghz_decode_raw",
                description="Decode a raw Sub-GHz capture file (.sub) and identify the protocol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to .sub file on Flipper (e.g., '/ext/subghz/capture.sub')",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        handlers = {
            "subghz_tx": self._tx,
            "subghz_tx_from_file": self._tx_from_file,
            "subghz_rx": self._rx,
            "subghz_decode_raw": self._decode_raw,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _tx(self, args: dict) -> Sequence[TextContent]:
        hex_key = args["hex_key"]
        freq = args.get("frequency", 433920000)
        te = args.get("te", 403)
        repeat = args.get("repeat", 10)
        try:
            result = await self.flipper.run_cli(
                f"subghz tx {hex_key} {freq} {te} {repeat}"
            )
            return [TextContent(type="text", text=f"Sub-GHz TX complete. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Sub-GHz TX failed: {e}")]

    async def _tx_from_file(self, args: dict) -> Sequence[TextContent]:
        file_path = args["file_path"]
        repeat = args.get("repeat", 1)
        try:
            result = await self.flipper.run_cli(
                f"subghz tx_from_file {file_path} {repeat}"
            )
            return [TextContent(type="text", text=f"Sub-GHz file TX complete. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Sub-GHz file TX failed: {e}")]

    async def _rx(self, args: dict) -> Sequence[TextContent]:
        freq = args.get("frequency", 433920000)
        duration = args.get("duration", 5.0)
        raw = args.get("raw", False)
        cmd = "subghz rx_raw" if raw else "subghz rx"
        try:
            result = await self.flipper.run_cli(f"{cmd} {freq}", timeout=duration + 2)
            return [TextContent(type="text", text=f"Sub-GHz RX capture:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Sub-GHz RX failed: {e}")]

    async def _decode_raw(self, args: dict) -> Sequence[TextContent]:
        file_path = args["file_path"]
        try:
            result = await self.flipper.run_cli(f"subghz decode_raw {file_path}")
            return [TextContent(type="text", text=f"Sub-GHz decode result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Sub-GHz decode failed: {e}")]
