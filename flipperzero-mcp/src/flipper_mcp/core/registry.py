"""Module registry for discovering and managing Flipper MCP modules."""

import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Type
from importlib import import_module
import inspect
import pkgutil

from mcp.types import Tool, TextContent
from ..modules.base_module import FlipperModule
from .audit import AuditLogger
from .risk import classify_tool


class ModuleRegistry:
    """
    Central registry for all Flipper MCP modules.
    
    Handles loading, initialization, and lifecycle management.
    Automatically discovers modules in the modules package.
    """
    
    def __init__(self, flipper_client: Any, audit_logger: Optional[AuditLogger] = None):
        """
        Initialize module registry.

        Args:
            flipper_client: Flipper client instance to pass to modules
            audit_logger: Optional audit logger for recording tool calls.
                          If None, a default AuditLogger is created.
        """
        self.flipper = flipper_client
        self.modules: Dict[str, FlipperModule] = {}
        self.load_order: List[str] = []
        self.audit = audit_logger or AuditLogger()
    
    def discover_modules(self, search_paths: List[str] | None = None) -> None:
        """
        Auto-discover modules in specified paths.
        
        By default, searches src/flipper_mcp/modules/ for module packages.
        Each module package should contain a module.py with a FlipperModule subclass.
        
        Args:
            search_paths: Optional list of package paths to search
        """
        if search_paths is None:
            search_paths = ['flipper_mcp.modules']
        
        for path in search_paths:
            try:
                package = import_module(path)
                package_dir = package.__path__
                
                # Iterate through subpackages
                for importer, modname, ispkg in pkgutil.iter_modules(package_dir):
                    if not ispkg or modname.startswith('_'):
                        continue
                    
                    try:
                        # Try to import module.py from the package
                        module_path = f"{path}.{modname}.module"
                        submodule = import_module(module_path)
                        
                        # Find FlipperModule subclasses
                        for name, obj in inspect.getmembers(submodule, inspect.isclass):
                            if (issubclass(obj, FlipperModule) and 
                                obj is not FlipperModule and
                                not inspect.isabstract(obj)):
                                
                                # Found a module class!
                                self.register_module(obj)
                                
                    except (ImportError, AttributeError) as e:
                        print(f"⚠️  Could not load module {modname}: {e}", file=sys.stderr)
                        
            except ImportError as e:
                print(f"⚠️  Could not import package {path}: {e}", file=sys.stderr)
    
    def register_module(self, module_class: Type[FlipperModule]) -> None:
        """
        Register a module class.
        
        Args:
            module_class: FlipperModule subclass to register
        """
        try:
            # Instantiate the module
            module = module_class(self.flipper)
            
            # Validate environment
            is_valid, error = module.validate_environment()
            if not is_valid:
                print(f"⚠️  Module {module.name} not loaded: {error}", file=sys.stderr)
                return
            
            # Check dependencies
            missing_deps = [
                dep for dep in module.get_dependencies() 
                if dep not in self.modules
            ]
            
            if missing_deps:
                print(f"⚠️  Module {module.name} missing dependencies: {missing_deps}", file=sys.stderr)
                return
            
            # Register module
            self.modules[module.name] = module
            self.load_order.append(module.name)
            print(f"✓ Registered module: {module.name} v{module.version}", file=sys.stderr)
            
        except Exception as e:
            print(f"✗ Failed to register module: {e}", file=sys.stderr)
    
    async def load_all(self) -> None:
        """Load all registered modules."""
        for name in self.load_order:
            module = self.modules[name]
            try:
                await module.on_load()
                print(f"✓ Loaded: {name}", file=sys.stderr)
            except Exception as e:
                print(f"✗ Failed to load {name}: {e}", file=sys.stderr)
                module.enabled = False
    
    async def unload_all(self) -> None:
        """Unload all modules."""
        for name in reversed(self.load_order):
            module = self.modules[name]
            try:
                await module.on_unload()
            except Exception as e:
                print(f"⚠️  Error unloading {name}: {e}", file=sys.stderr)
    
    def get_all_tools(self) -> List[Tool]:
        """
        Collect tools from all enabled modules.
        
        Returns:
            List of all tools from enabled modules
        """
        tools = []
        for module in self.modules.values():
            if module.enabled:
                try:
                    tools.extend(module.get_tools())
                except Exception as e:
                    print(f"⚠️  Error getting tools from {module.name}: {e}", file=sys.stderr)
        return tools
    
    async def route_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        """
        Route tool call to appropriate module.

        Classifies risk level, executes the tool, and logs the call
        to the audit logger.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        risk_level = classify_tool(tool_name)
        args_dict = arguments if isinstance(arguments, dict) else {}
        start_time = time.monotonic()
        success = False
        result_text = ""

        try:
            # Find which module owns this tool
            for module in self.modules.values():
                if not module.enabled:
                    continue

                try:
                    tool_names = [tool.name for tool in module.get_tools()]
                    if tool_name in tool_names:
                        result = await module.handle_tool_call(tool_name, arguments)
                        success = True
                        result_text = result[0].text if result else ""
                        return result
                except Exception as e:
                    result_text = f"Error in module {module.name}: {str(e)}"
                    return [TextContent(
                        type="text",
                        text=f"Error in module {module.name}: {str(e)}"
                    )]

            # Tool not found
            result_text = f"Error: Tool '{tool_name}' not found in any module"
            return [TextContent(
                type="text",
                text=f"Error: Tool '{tool_name}' not found in any module"
            )]

        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.audit.log_call(
                tool_name=tool_name,
                arguments=args_dict,
                risk_level=risk_level,
                result=result_text,
                duration_ms=duration_ms,
                success=success,
            )
    
    def get_module(self, name: str) -> FlipperModule | None:
        """
        Get module by name.
        
        Args:
            name: Module name
            
        Returns:
            Module instance or None
        """
        return self.modules.get(name)
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """
        List all registered modules.
        
        Returns:
            List of module info dicts
        """
        return [
            {
                "name": module.name,
                "version": module.version,
                "description": module.description,
                "enabled": module.enabled,
                "tools": len(module.get_tools()) if module.enabled else 0
            }
            for module in self.modules.values()
        ]
