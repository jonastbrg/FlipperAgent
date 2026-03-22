"""RFID (125kHz) module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule

RFID_KEY_TYPES = [
    "EM4100", "H10301", "Indala26", "IoProxXSF", "AWID",
    "FDX-A", "FDX-B", "HIDProx", "HIDExt", "Pyramid",
    "Viking", "Jablotron", "Paradox", "PAC/Stanley", "Keri", "Gallagher",
]


class RFIDModule(FlipperModule):
    """125kHz RFID tag read, emulate, and write operations."""

    @property
    def name(self) -> str:
        return "rfid"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "RFID 125kHz: read, emulate, and write tags (EM4100, HID, Indala, etc.)"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="rfid_read",
                description="Read a 125kHz RFID tag. Hold tag near Flipper's RFID coil.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Read duration in seconds (default: 5)",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="rfid_emulate",
                description="Emulate a 125kHz RFID tag with specified type and data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key_type": {
                            "type": "string",
                            "enum": RFID_KEY_TYPES,
                            "description": "RFID key type (e.g., EM4100, HIDProx)",
                        },
                        "key_data": {
                            "type": "string",
                            "description": "Key data in hex (e.g., 'DEADBEEF01')",
                        },
                        "duration": {
                            "type": "number",
                            "default": 10.0,
                            "description": "Emulation duration in seconds (default: 10)",
                        },
                    },
                    "required": ["key_type", "key_data"],
                },
            ),
            Tool(
                name="rfid_write",
                description="Write data to a 125kHz RFID tag. Hold writable tag near Flipper.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key_type": {
                            "type": "string",
                            "enum": RFID_KEY_TYPES,
                            "description": "RFID key type",
                        },
                        "key_data": {
                            "type": "string",
                            "description": "Key data in hex",
                        },
                        "duration": {
                            "type": "number",
                            "default": 10.0,
                            "description": "Write timeout in seconds (default: 10)",
                        },
                    },
                    "required": ["key_type", "key_data"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        handlers = {
            "rfid_read": self._read,
            "rfid_emulate": self._emulate,
            "rfid_write": self._write,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _read(self, args: dict) -> Sequence[TextContent]:
        duration = args.get("duration", 5.0)
        try:
            result = await self.flipper.run_cli("rfid read", timeout=duration + 2)
            return [TextContent(type="text", text=f"RFID read result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"RFID read failed: {e}")]

    async def _emulate(self, args: dict) -> Sequence[TextContent]:
        key_type = args["key_type"]
        key_data = args["key_data"]
        duration = args.get("duration", 10.0)
        try:
            result = await self.flipper.run_cli(
                f"rfid emulate {key_type} {key_data}", timeout=duration + 2
            )
            return [TextContent(type="text", text=f"RFID emulating {key_type}. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"RFID emulate failed: {e}")]

    async def _write(self, args: dict) -> Sequence[TextContent]:
        key_type = args["key_type"]
        key_data = args["key_data"]
        duration = args.get("duration", 10.0)
        try:
            result = await self.flipper.run_cli(
                f"rfid write {key_type} {key_data}", timeout=duration + 2
            )
            return [TextContent(type="text", text=f"RFID write result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"RFID write failed: {e}")]
