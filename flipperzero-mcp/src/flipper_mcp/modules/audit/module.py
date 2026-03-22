"""Audit log query module for Flipper Zero MCP."""

import json
from typing import Any, List, Sequence
from mcp.types import Tool, TextContent

from ..base_module import FlipperModule


class AuditModule(FlipperModule):
    """Query the audit log of all MCP tool invocations."""

    @property
    def name(self) -> str:
        return "audit"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Query audit log of all Flipper MCP tool calls"

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="audit_query",
                description=(
                    "Query the audit log. Returns recent tool invocations with "
                    "timestamps, risk levels, results, and durations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "description": "Max entries to return (default: 20)",
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "Filter by tool name (optional)",
                        },
                        "risk_level": {
                            "type": "string",
                            "enum": ["LOW", "MEDIUM", "HIGH", "BLOCKED"],
                            "description": "Filter by risk level (optional)",
                        },
                    },
                    "required": [],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        if tool_name != "audit_query":
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]

        # Get audit logger from the registry (injected via flipper_client or module config)
        audit_logger = getattr(self.flipper, '_audit_logger', None)
        if audit_logger is None:
            return [TextContent(type="text", text="Audit logging not available.")]

        limit = arguments.get("limit", 20)
        tool_filter = arguments.get("tool_name")
        risk_filter = arguments.get("risk_level")

        # Convert string risk level to enum if provided
        if risk_filter and isinstance(risk_filter, str):
            try:
                from ...core.risk import RiskLevel
                risk_filter = RiskLevel(risk_filter)
            except ValueError:
                return [TextContent(type="text", text=f"Invalid risk level: {risk_filter}")]

        entries = audit_logger.get_log(
            limit=limit,
            tool_name=tool_filter,
            risk_level=risk_filter,
        )

        if not entries:
            return [TextContent(type="text", text="No audit entries found.")]

        formatted = json.dumps(entries, indent=2, default=str)
        return [
            TextContent(
                type="text",
                text=f"Audit log ({len(entries)} entries):\n{formatted}",
            )
        ]
