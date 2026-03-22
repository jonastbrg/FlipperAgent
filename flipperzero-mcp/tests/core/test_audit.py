"""Tests for audit logging system."""
import pytest
from flipper_mcp.core.audit import AuditLogger
from flipper_mcp.core.risk import RiskLevel


class TestAuditLogger:
    def test_log_and_retrieve(self):
        logger = AuditLogger()
        logger.log_call("led_set", {"led": "r"}, RiskLevel.LOW, "OK", 10, True)
        entries = logger.get_log(limit=10)
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "led_set"
        assert entries[0]["success"] is True

    def test_ring_buffer_limit(self):
        logger = AuditLogger()
        # Override the max for testing
        logger._buffer = __import__('collections').deque(maxlen=5)
        for i in range(10):
            logger.log_call(f"tool_{i}", {}, RiskLevel.LOW, "OK", 1, True)
        entries = logger.get_log(limit=100)
        assert len(entries) == 5

    def test_filter_by_tool_name(self):
        logger = AuditLogger()
        logger.log_call("led_set", {}, RiskLevel.LOW, "OK", 1, True)
        logger.log_call("subghz_tx", {}, RiskLevel.HIGH, "OK", 2, True)
        logger.log_call("led_set", {}, RiskLevel.LOW, "OK", 3, True)
        entries = logger.get_log(tool_name="led_set")
        assert len(entries) == 2
        assert all(e["tool_name"] == "led_set" for e in entries)

    def test_filter_by_risk_level(self):
        logger = AuditLogger()
        logger.log_call("led_set", {}, RiskLevel.LOW, "OK", 1, True)
        logger.log_call("subghz_tx", {}, RiskLevel.HIGH, "done", 2, True)
        entries = logger.get_log(risk_level="HIGH")
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "subghz_tx"

    def test_session_id_consistent(self):
        logger = AuditLogger()
        logger.log_call("a", {}, RiskLevel.LOW, "", 1, True)
        logger.log_call("b", {}, RiskLevel.LOW, "", 1, True)
        entries = logger.get_log()
        assert entries[0]["session_id"] == entries[1]["session_id"]

    def test_entry_has_timestamp(self):
        logger = AuditLogger()
        logger.log_call("led_set", {}, RiskLevel.LOW, "OK", 5, True)
        entries = logger.get_log()
        assert "timestamp" in entries[0]
        assert "T" in entries[0]["timestamp"]  # ISO format


class TestRiskClassification:
    def test_known_low_tool(self):
        from flipper_mcp.core.risk import classify_tool
        assert classify_tool("led_set") == RiskLevel.LOW

    def test_known_high_tool(self):
        from flipper_mcp.core.risk import classify_tool
        assert classify_tool("subghz_tx") == RiskLevel.HIGH

    def test_unknown_defaults_medium(self):
        from flipper_mcp.core.risk import classify_tool
        assert classify_tool("totally_unknown_tool") == RiskLevel.MEDIUM

    def test_blocked_paths(self):
        from flipper_mcp.core.risk import is_path_blocked
        assert is_path_blocked("/int/some/file") is True
        assert is_path_blocked("/ext/subghz/test.sub") is False
        assert is_path_blocked("firmware.key") is True
