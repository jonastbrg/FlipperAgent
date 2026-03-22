"""Tests for BadUSB module."""

import pytest
from unittest.mock import Mock, AsyncMock
from flipper_mcp.modules.badusb.module import BadUSBModule
from flipper_mcp.modules.badusb.generator import DuckyScriptGenerator
from flipper_mcp.modules.badusb.validator import ScriptValidator


@pytest.fixture
def mock_flipper():
    """Create mock Flipper client."""
    client = Mock()
    client.check_sd_card_available = AsyncMock(return_value=True)
    client.storage = Mock()
    client.storage.list = AsyncMock(return_value=["test.txt", "demo.txt"])
    client.storage.read = AsyncMock(return_value="REM Test script\nSTRING Hello")
    client.storage.write = AsyncMock(return_value=True)
    client.app = Mock()
    client.app.launch = AsyncMock(return_value=True)
    return client


def test_badusb_module_properties(mock_flipper):
    """Test BadUSB module properties."""
    module = BadUSBModule(mock_flipper)
    
    assert module.name == "badusb"
    assert module.version == "1.1.0"
    assert "BadUSB" in module.description


def test_badusb_tools(mock_flipper):
    """Test BadUSB tools registration."""
    module = BadUSBModule(mock_flipper)
    tools = module.get_tools()
    
    assert len(tools) == 10
    tool_names = [tool.name for tool in tools]
    assert "badusb_list" in tool_names
    assert "badusb_read" in tool_names
    assert "badusb_generate" in tool_names
    assert "badusb_validate" in tool_names
    assert "badusb_write" in tool_names
    assert "badusb_delete" in tool_names
    assert "badusb_diff" in tool_names
    assert "badusb_rename" in tool_names
    assert "badusb_execute" in tool_names
    assert "badusb_workflow" in tool_names


@pytest.mark.asyncio
async def test_badusb_list(mock_flipper):
    """Test listing BadUSB scripts."""
    module = BadUSBModule(mock_flipper)
    
    result = await module.handle_tool_call("badusb_list", {})
    
    assert len(result) == 1
    assert "test.txt" in result[0].text
    assert "demo.txt" in result[0].text


@pytest.mark.asyncio
async def test_badusb_read(mock_flipper):
    """Test reading BadUSB script."""
    module = BadUSBModule(mock_flipper)
    
    result = await module.handle_tool_call("badusb_read", {"filename": "test.txt"})
    
    assert len(result) == 1
    assert "Hello" in result[0].text


@pytest.mark.asyncio
async def test_badusb_generate(mock_flipper):
    """Test generating BadUSB script."""
    module = BadUSBModule(mock_flipper)
    
    result = await module.handle_tool_call(
        "badusb_generate",
        {
            "description": "open notepad",
            "target_os": "windows",
            "filename": "test.txt"
        }
    )
    
    assert len(result) == 1
    assert "generated" in result[0].text.lower()


@pytest.mark.asyncio
async def test_badusb_execute_without_confirm(mock_flipper):
    """Test executing without confirmation."""
    module = BadUSBModule(mock_flipper)
    
    result = await module.handle_tool_call(
        "badusb_execute",
        {"filename": "test.txt", "confirm": False}
    )
    
    assert len(result) == 1
    assert "blocked" in result[0].text.lower()


@pytest.mark.asyncio
async def test_badusb_execute_with_confirm(mock_flipper):
    """Test executing with confirmation."""
    module = BadUSBModule(mock_flipper)
    
    result = await module.handle_tool_call(
        "badusb_execute",
        {"filename": "test.txt", "confirm": True}
    )
    
    assert len(result) == 1
    mock_flipper.app.launch.assert_called_once()


def test_duckyscript_generator():
    """Test DuckyScript generator."""
    generator = DuckyScriptGenerator()
    
    # Test Windows generation
    script = generator.generate("open notepad", "windows")
    assert "notepad" in script.lower()
    assert "GUI r" in script or "DELAY" in script
    
    # Test macOS generation
    script = generator.generate("open terminal", "macos")
    assert "terminal" in script.lower()
    assert "COMMAND SPACE" in script or "DELAY" in script
    
    # Test Linux generation
    script = generator.generate("open terminal", "linux")
    assert "CTRL ALT t" in script or "DELAY" in script


def test_script_validator():
    """Test script validator."""
    validator = ScriptValidator()
    
    # Test valid script
    safe_script = "REM Test\nDELAY 500\nSTRING Hello"
    is_valid, error = validator.validate(safe_script)
    assert is_valid
    
    # Test dangerous script
    dangerous_script = "rm -rf /"
    is_valid, error = validator.validate(dangerous_script)
    assert not is_valid
    assert error != ""
