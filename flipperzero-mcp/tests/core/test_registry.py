"""Tests for core module registry."""

import pytest
from unittest.mock import Mock, AsyncMock
from flipper_mcp.core.registry import ModuleRegistry
from flipper_mcp.modules.base_module import FlipperModule
from mcp.types import Tool, TextContent
from typing import List, Any, Sequence


class TestModule(FlipperModule):
    """Test module for registry tests."""
    
    @property
    def name(self) -> str:
        return "test"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Test module"
    
    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="test_action",
                description="Test action",
                inputSchema={"type": "object", "properties": {}}
            )
        ]
    
    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        return [TextContent(type="text", text=f"Test: {tool_name}")]


@pytest.fixture
def mock_flipper():
    """Create mock Flipper client."""
    client = Mock()
    client.connected = True
    return client


def test_registry_initialization(mock_flipper):
    """Test registry initialization."""
    registry = ModuleRegistry(mock_flipper)
    assert registry.flipper == mock_flipper
    assert len(registry.modules) == 0
    assert len(registry.load_order) == 0


def test_register_module(mock_flipper):
    """Test module registration."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    assert "test" in registry.modules
    assert "test" in registry.load_order
    assert registry.modules["test"].name == "test"


@pytest.mark.asyncio
async def test_load_all(mock_flipper):
    """Test loading all modules."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    await registry.load_all()
    
    assert registry.modules["test"].enabled


def test_get_all_tools(mock_flipper):
    """Test getting all tools."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    tools = registry.get_all_tools()
    
    assert len(tools) == 1
    assert tools[0].name == "test_action"


@pytest.mark.asyncio
async def test_route_tool_call(mock_flipper):
    """Test routing tool calls."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    result = await registry.route_tool_call("test_action", {})
    
    assert len(result) == 1
    assert "Test: test_action" in result[0].text


@pytest.mark.asyncio
async def test_route_unknown_tool(mock_flipper):
    """Test routing unknown tool."""
    registry = ModuleRegistry(mock_flipper)
    
    result = await registry.route_tool_call("unknown_tool", {})
    
    assert len(result) == 1
    assert "not found" in result[0].text.lower()


def test_get_module(mock_flipper):
    """Test getting module by name."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    module = registry.get_module("test")
    
    assert module is not None
    assert module.name == "test"


def test_list_modules(mock_flipper):
    """Test listing modules."""
    registry = ModuleRegistry(mock_flipper)
    registry.register_module(TestModule)
    
    modules = registry.list_modules()
    
    assert len(modules) == 1
    assert modules[0]["name"] == "test"
    assert modules[0]["version"] == "1.0.0"
    assert modules[0]["enabled"] == True
