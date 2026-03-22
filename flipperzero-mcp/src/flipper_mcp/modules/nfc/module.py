"""NFC module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class NFCModule(FlipperModule):
    """NFC tag detection, emulation, and field operations."""

    @property
    def name(self) -> str:
        return "nfc"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "NFC: detect tags, emulate cards, activate NFC field"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="nfc_detect",
                description="Detect an NFC tag. Hold a tag near the Flipper's NFC coil.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Scan duration in seconds (default: 5)",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="nfc_emulate",
                description="Emulate an NFC tag. The Flipper will act as an NFC card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 10.0,
                            "description": "Emulation duration in seconds (default: 10)",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="nfc_field",
                description="Activate NFC field to detect nearby NFC readers.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Field activation duration in seconds (default: 5)",
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
            "nfc_detect": self._detect,
            "nfc_emulate": self._emulate,
            "nfc_field": self._field,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _detect(self, args: dict) -> Sequence[TextContent]:
        duration = args.get("duration", 5.0)
        try:
            result = await self.flipper.run_cli("nfc detect", timeout=duration + 2)
            return [TextContent(type="text", text=f"NFC detect result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"NFC detect failed: {e}")]

    async def _emulate(self, args: dict) -> Sequence[TextContent]:
        duration = args.get("duration", 10.0)
        try:
            result = await self.flipper.run_cli("nfc emulate", timeout=duration + 2)
            return [TextContent(type="text", text=f"NFC emulation result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"NFC emulate failed: {e}")]

    async def _field(self, args: dict) -> Sequence[TextContent]:
        duration = args.get("duration", 5.0)
        try:
            result = await self.flipper.run_cli("nfc field", timeout=duration + 2)
            return [TextContent(type="text", text=f"NFC field result:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"NFC field failed: {e}")]
