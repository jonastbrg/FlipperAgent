"""Tests for IR module."""
from flipper_mcp.modules.ir.module import IRModule


def test_module_properties():
    module = IRModule(flipper_client=None)
    assert module.name == "ir"
    assert len(module.get_tools()) == 3


def test_tool_names():
    module = IRModule(flipper_client=None)
    names = [t.name for t in module.get_tools()]
    assert "ir_tx" in names
    assert "ir_tx_raw" in names
    assert "ir_rx" in names


def test_hex_format():
    """Test hex byte formatting for IR addresses/commands."""
    result = IRModule._format_hex_bytes("04")
    assert result == "04 00 00 00"

    result = IRModule._format_hex_bytes("AB")
    assert result == "AB 00 00 00"


def test_tx_schema_has_protocol_enum():
    module = IRModule(flipper_client=None)
    tx_tool = next(t for t in module.get_tools() if t.name == "ir_tx")
    protocols = tx_tool.inputSchema["properties"]["protocol"]["enum"]
    assert "NEC" in protocols
    assert "Samsung32" in protocols
    assert "RC6" in protocols
