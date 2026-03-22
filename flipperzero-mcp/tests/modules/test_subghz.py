"""Tests for SubGHz module tool definitions."""
from flipper_mcp.modules.subghz.module import SubGHzModule


def test_module_properties():
    module = SubGHzModule(flipper_client=None)
    assert module.name == "subghz"
    assert module.version == "1.0.0"


def test_tool_count():
    module = SubGHzModule(flipper_client=None)
    tools = module.get_tools()
    assert len(tools) == 4


def test_tool_names():
    module = SubGHzModule(flipper_client=None)
    tool_names = [t.name for t in module.get_tools()]
    assert "subghz_tx" in tool_names
    assert "subghz_rx" in tool_names
    assert "subghz_decode_raw" in tool_names
    assert "subghz_tx_from_file" in tool_names


def test_tx_schema_has_required_fields():
    module = SubGHzModule(flipper_client=None)
    tx_tool = next(t for t in module.get_tools() if t.name == "subghz_tx")
    schema = tx_tool.inputSchema
    assert "hex_key" in schema["properties"]
    assert "frequency" in schema["properties"]
    assert "hex_key" in schema["required"]
