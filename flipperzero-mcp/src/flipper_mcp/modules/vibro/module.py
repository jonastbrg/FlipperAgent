"""Vibration motor module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class VibroModule(FlipperModule):
    """Control Flipper Zero vibration motor."""

    @property
    def name(self) -> str:
        return "vibro"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Control Flipper Zero vibration motor"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="vibro_set",
                description="Turn Flipper Zero vibration motor on or off.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "True to vibrate, False to stop",
                        }
                    },
                    "required": ["enabled"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        if tool_name == "vibro_set":
            enabled = arguments.get("enabled", False)
            value = "1" if enabled else "0"
            state = "on" if enabled else "off"
            return await self._run_cli_tool(f"vibro {value}", f"Vibration {state}")
        return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
