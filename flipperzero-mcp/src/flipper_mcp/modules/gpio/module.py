"""GPIO module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class GPIOModule(FlipperModule):
    """GPIO pin read, write, and mode control."""

    @property
    def name(self) -> str:
        return "gpio"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "GPIO: read pins, set output values, configure pin modes"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="gpio_read",
                description="Read the state of a GPIO pin.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "string",
                            "description": "Pin name (e.g., 'PA7', 'PA6', 'PA4', 'PB3', 'PB2', 'PC3', 'PC1', 'PC0')",
                        }
                    },
                    "required": ["pin"],
                },
            ),
            Tool(
                name="gpio_set",
                description="Set a GPIO pin output value (0 or 1).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pin": {"type": "string", "description": "Pin name"},
                        "value": {
                            "type": "integer",
                            "enum": [0, 1],
                            "description": "Pin value: 0 (low) or 1 (high)",
                        },
                    },
                    "required": ["pin", "value"],
                },
            ),
            Tool(
                name="gpio_mode",
                description="Set GPIO pin mode (input or output).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pin": {"type": "string", "description": "Pin name"},
                        "mode": {
                            "type": "integer",
                            "enum": [0, 1],
                            "description": "Mode: 0 (input) or 1 (output)",
                        },
                    },
                    "required": ["pin", "mode"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        handlers = {
            "gpio_read": self._read,
            "gpio_set": self._set,
            "gpio_mode": self._mode,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _read(self, args: dict) -> Sequence[TextContent]:
        pin = args["pin"]
        try:
            result = await self.flipper.run_cli(f"gpio read {pin}")
            return [TextContent(type="text", text=f"GPIO {pin}: {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"GPIO read failed: {e}")]

    async def _set(self, args: dict) -> Sequence[TextContent]:
        pin = args["pin"]
        value = args["value"]
        try:
            result = await self.flipper.run_cli(f"gpio set {pin} {value}")
            return [TextContent(type="text", text=f"GPIO {pin} set to {value}. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"GPIO set failed: {e}")]

    async def _mode(self, args: dict) -> Sequence[TextContent]:
        pin = args["pin"]
        mode = args["mode"]
        mode_name = "output" if mode == 1 else "input"
        try:
            result = await self.flipper.run_cli(f"gpio mode {pin} {mode}")
            return [TextContent(type="text", text=f"GPIO {pin} mode set to {mode_name}. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"GPIO mode failed: {e}")]
