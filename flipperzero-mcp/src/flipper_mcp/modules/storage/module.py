"""Storage module for Flipper Zero MCP — wraps existing protobuf file I/O."""

from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule
from ...core.risk import validate_flipper_path


class StorageModule(FlipperModule):
    """File system operations via protobuf RPC (read, write, list, delete, mkdir)."""

    @property
    def name(self) -> str:
        return "storage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Flipper Zero file system: list, read, write, delete, mkdir, storage info"

    def requires_sd_card(self) -> bool:
        return True

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="storage_list",
                description="List files and directories at a path on the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "default": "/ext",
                            "description": "Directory path (default: /ext)",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="storage_read",
                description="Read the contents of a file on the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path (e.g., '/ext/subghz/signal.sub')",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_write",
                description="Write content to a file on the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to write to",
                        },
                        "content": {
                            "type": "string",
                            "description": "File content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            ),
            Tool(
                name="storage_delete",
                description="Delete a file or directory from the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to delete",
                        },
                        "recursive": {
                            "type": "boolean",
                            "default": False,
                            "description": "Delete recursively (for directories)",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_mkdir",
                description="Create a directory on the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to create",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="storage_info",
                description="Get storage usage info (total/free space) for the Flipper SD card.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "default": "/ext",
                            "description": "Storage path (default: /ext for SD card)",
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
            "storage_list": self._list,
            "storage_read": self._read,
            "storage_write": self._write,
            "storage_delete": self._delete,
            "storage_mkdir": self._mkdir,
            "storage_info": self._info,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        return await handler(arguments)

    async def _list(self, args: dict) -> Sequence[TextContent]:
        path = args.get("path", "/ext")
        try:
            files = await self.flipper.storage.list(path)
            if not files:
                return [TextContent(type="text", text=f"Directory '{path}' is empty or not found.")]
            listing = "\n".join(f"  {f}" for f in files)
            return [TextContent(type="text", text=f"Contents of {path}:\n{listing}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage list failed: {e}")]

    async def _read(self, args: dict) -> Sequence[TextContent]:
        path = args["path"]
        try:
            validate_flipper_path(path)
        except ValueError as e:
            return [TextContent(type="text", text=f"Blocked: {e}")]
        try:
            content = await self.flipper.storage.read(path)
            if not content:
                return [TextContent(type="text", text=f"File '{path}' is empty or not found.")]
            return [TextContent(type="text", text=f"Contents of {path}:\n{content}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage read failed: {e}")]

    async def _write(self, args: dict) -> Sequence[TextContent]:
        path = args["path"]
        content = args["content"]
        try:
            validate_flipper_path(path)
        except ValueError as e:
            return [TextContent(type="text", text=f"Blocked: {e}")]
        try:
            success = await self.flipper.storage.write(path, content)
            if success:
                return [TextContent(type="text", text=f"Written {len(content)} bytes to {path}")]
            return [TextContent(type="text", text=f"Write to {path} failed (no error details).")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage write failed: {e}")]

    async def _delete(self, args: dict) -> Sequence[TextContent]:
        path = args["path"]
        recursive = args.get("recursive", False)
        try:
            validate_flipper_path(path)
        except ValueError as e:
            return [TextContent(type="text", text=f"Blocked: {e}")]
        try:
            success = await self.flipper.storage.delete(path, recursive=recursive)
            if success:
                return [TextContent(type="text", text=f"Deleted {path}")]
            return [TextContent(type="text", text=f"Delete {path} failed.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage delete failed: {e}")]

    async def _mkdir(self, args: dict) -> Sequence[TextContent]:
        path = args["path"]
        try:
            success = await self.flipper.storage.mkdir(path)
            if success:
                return [TextContent(type="text", text=f"Created directory {path}")]
            return [TextContent(type="text", text=f"Mkdir {path} failed.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage mkdir failed: {e}")]

    async def _info(self, args: dict) -> Sequence[TextContent]:
        path = args.get("path", "/ext")
        try:
            info = await self.flipper.storage.info(path)
            if info:
                total = info.get("total_space", 0)
                free = info.get("free_space", 0)
                used = total - free
                return [
                    TextContent(
                        type="text",
                        text=(
                            f"Storage info for {path}:\n"
                            f"  Total: {total:,} bytes ({total // 1024 // 1024} MB)\n"
                            f"  Free:  {free:,} bytes ({free // 1024 // 1024} MB)\n"
                            f"  Used:  {used:,} bytes ({used // 1024 // 1024} MB)"
                        ),
                    )
                ]
            return [TextContent(type="text", text=f"Storage info unavailable for {path}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Storage info failed: {e}")]
