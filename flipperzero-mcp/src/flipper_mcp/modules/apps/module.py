"""Application launcher module for Flipper Zero MCP."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class AppsModule(FlipperModule):
    """List and launch Flipper Zero applications."""

    @property
    def name(self) -> str:
        return "apps"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "List installed apps and launch them by name"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="apps_list",
                description="List all available applications on the Flipper Zero.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="apps_launch",
                description=(
                    "Launch an application on the Flipper Zero by name. "
                    "Common apps: Sub-GHz, Infrared, NFC, 125 kHz RFID, iButton, "
                    "Bad USB, GPIO, Snake, U2F."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Application name to launch",
                        },
                        "args": {
                            "type": "string",
                            "default": "",
                            "description": "Optional arguments for the app",
                        },
                    },
                    "required": ["app_name"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        if tool_name == "apps_list":
            return await self._list_apps()
        elif tool_name == "apps_launch":
            return await self._launch_app(arguments)
        return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]

    async def _list_apps(self) -> Sequence[TextContent]:
        try:
            result = await self.flipper.run_cli("loader list")
            return [TextContent(type="text", text=f"Installed apps:\n{result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"App list failed: {e}")]

    async def _launch_app(self, args: dict) -> Sequence[TextContent]:
        app_name = args["app_name"]
        app_args = args.get("args", "")
        try:
            # Try protobuf app_start first (more reliable)
            if self.flipper.rpc:
                success = await self.flipper.rpc.app_start(app_name, args=app_args)
                if success:
                    return [TextContent(type="text", text=f"Launched '{app_name}' via RPC.")]
            # Fallback to CLI
            cmd = f"loader open {app_name}"
            if app_args:
                cmd += f" {app_args}"
            result = await self.flipper.run_cli(cmd)
            return [TextContent(type="text", text=f"Launched '{app_name}'. {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"App launch failed: {e}")]
