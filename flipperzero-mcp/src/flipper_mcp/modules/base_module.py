"""Base module interface for Flipper MCP modules."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Sequence
from mcp.types import Tool, TextContent
from ..core.risk import RiskLevel


class FlipperModule(ABC):
    """
    Base class for all Flipper Zero MCP modules.
    
    Modules are self-contained units that:
    1. Register tools with the MCP server
    2. Handle tool execution
    3. Manage their own state
    4. Can depend on core transport layer
    
    Example:
        class MyModule(FlipperModule):
            @property
            def name(self) -> str:
                return "mymodule"
            
            def get_tools(self) -> List[Tool]:
                return [Tool(...)]
            
            async def handle_tool_call(self, tool_name, arguments):
                # Handle the tool call
                pass
    """
    
    def __init__(self, flipper_client: Any):
        """
        Initialize module with Flipper client.
        
        Args:
            flipper_client: Core Flipper RPC client (transport-agnostic)
        """
        self.flipper = flipper_client
        self.enabled = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Module name (e.g., 'badusb', 'subghz').
        
        Returns:
            Module name
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """
        Module version (semver).
        
        Returns:
            Version string
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Short description of module capabilities.
        
        Returns:
            Description string
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """
        Return list of MCP tools this module provides.
        
        Tools are registered with the MCP server and become
        callable by AI assistants.
        
        Returns:
            List of Tool objects with name, description, and schema
        """
        pass
    
    @abstractmethod
    async def handle_tool_call(self, tool_name: str, arguments: Any) -> Sequence[TextContent]:
        """
        Handle execution of a tool from this module.
        
        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments from AI assistant
            
        Returns:
            List of TextContent responses
        """
        pass
    
    async def on_load(self) -> None:
        """
        Called when module is loaded.
        Use for initialization, validation, etc.
        """
        pass
    
    async def on_unload(self) -> None:
        """
        Called when module is unloaded.
        Use for cleanup.
        """
        pass
    
    def get_dependencies(self) -> List[str]:
        """
        Return list of module names this module depends on.
        
        Returns:
            List of module names (e.g., ['storage', 'system'])
        """
        return []
    
    def validate_environment(self) -> tuple[bool, str]:
        """
        Check if environment is suitable for this module.
        
        Returns:
            (is_valid, error_message)
        """
        return True, ""
    
    def requires_sd_card(self) -> bool:
        """
        Return whether this module requires SD card to function.

        Modules that need to write files to /ext/* paths should
        override this to return True. The module system will check
        SD card availability before executing operations that require it.

        Returns:
            True if module requires SD card, False otherwise
        """
        return False  # Default: no SD card required

    async def _run_cli_tool(self, command: str, label: str, timeout: float = 5.0) -> Sequence[TextContent]:
        """Run a CLI command and return formatted MCP response."""
        try:
            result = await self.flipper.run_cli(command, timeout=timeout)
            return [TextContent(type="text", text=f"{label}: {result}" if result else label)]
        except Exception as e:
            return [TextContent(type="text", text=f"{label} failed: {e}")]

    async def _dispatch(
        self, tool_name: str, arguments: Any,
        handlers: dict, error_prefix: str = ""
    ) -> Sequence[TextContent]:
        """Dispatch a tool call to the correct handler with error wrapping.

        Eliminates the repeated dict-lookup + try/except pattern across modules.
        """
        handler = handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        try:
            return await handler(arguments)
        except Exception as e:
            prefix = f"{error_prefix}: " if error_prefix else ""
            return [TextContent(type="text", text=f"{prefix}{e}")]

    def get_risk_levels(self) -> Dict[str, RiskLevel]:
        """
        Return risk level overrides for this module's tools.

        Modules can override this to provide tool-specific risk levels
        that take precedence over the global TOOL_RISK_MAP. This is useful
        for modules that know their tools' risk profiles better than the
        static lookup table.

        Returns:
            Dict mapping tool name to RiskLevel, empty by default
        """
        return {}