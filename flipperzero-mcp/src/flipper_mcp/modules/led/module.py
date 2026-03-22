"""LED control module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class LEDModule(FlipperModule):
    """Control Flipper Zero LEDs (red, green, blue, backlight)."""

    @property
    def name(self) -> str:
        return "led"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Control Flipper Zero RGB LED and backlight"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="led_set",
                description=(
                    "Set a Flipper Zero LED brightness. "
                    "LED choices: 'r' (red), 'g' (green), 'b' (blue), 'bl' (backlight). "
                    "Value: 0-255."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "led": {
                            "type": "string",
                            "enum": ["r", "g", "b", "bl"],
                            "description": "LED to control: r, g, b, or bl (backlight)",
                        },
                        "value": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 255,
                            "description": "Brightness 0-255",
                        },
                    },
                    "required": ["led", "value"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        if tool_name == "led_set":
            return await self._set_led(arguments)
        return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]

    async def _set_led(self, args: dict) -> Sequence[TextContent]:
        led = args["led"]
        value = int(args["value"])
        if value < 0 or value > 255:
            return [TextContent(type="text", text="Value must be 0-255")]
        return await self._run_cli_tool(f"led {led} {value}", f"LED '{led}' set to {value}")
