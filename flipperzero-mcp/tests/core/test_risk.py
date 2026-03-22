"""Tests for risk classification."""
import pytest
from flipper_mcp.core.risk import classify_tool, RiskLevel, TOOL_RISK_MAP, is_path_blocked, validate_flipper_path


def test_all_42_tools_classified():
    """Every tool in the risk map should have a valid RiskLevel."""
    for tool_name, level in TOOL_RISK_MAP.items():
        assert isinstance(level, RiskLevel), f"{tool_name} has invalid level: {level}"


def test_high_risk_tools():
    """Verify RF transmission and tag manipulation are HIGH."""
    high_tools = ["subghz_tx", "subghz_tx_from_file", "nfc_emulate",
                  "rfid_emulate", "rfid_write", "badusb_execute"]
    for tool in high_tools:
        assert classify_tool(tool) == RiskLevel.HIGH, f"{tool} should be HIGH"


def test_low_risk_read_tools():
    """Verify read-only tools are LOW."""
    low_tools = ["gpio_read", "rfid_read", "nfc_detect", "ir_rx",
                 "subghz_rx", "storage_list", "storage_read", "led_set"]
    for tool in low_tools:
        assert classify_tool(tool) == RiskLevel.LOW, f"{tool} should be LOW"


def test_path_blocked_int():
    assert is_path_blocked("/int/firmware") is True
    assert is_path_blocked("/int/") is True


def test_path_not_blocked_internal_docs():
    """Regression: /internal_docs should NOT be blocked."""
    assert is_path_blocked("/internal_docs/readme.txt") is False


def test_path_blocked_key_suffix():
    assert is_path_blocked("/ext/creds.key") is True
    assert is_path_blocked("/ext/data.priv") is True


def test_validate_path_traversal():
    with pytest.raises(ValueError, match="traversal"):
        validate_flipper_path("/ext/../int/secret")


def test_validate_path_must_be_ext():
    with pytest.raises(ValueError, match="SD card"):
        validate_flipper_path("/tmp/evil")


def test_validate_path_ok():
    assert validate_flipper_path("/ext/subghz/signal.sub") == "/ext/subghz/signal.sub"
