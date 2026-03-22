"""Tests for CLI input sanitization."""
import pytest
from flipper_mcp.core.sanitize import sanitize_cli_input, sanitize_args_for_log


class TestSanitizeCLIInput:
    def test_clean_command_passes(self):
        assert sanitize_cli_input("led r 255") == "led r 255"

    def test_strips_semicolon(self):
        result = sanitize_cli_input("led r 255; reboot")
        assert ";" not in result

    def test_strips_pipe(self):
        result = sanitize_cli_input("gpio read PA7 | cat /etc/passwd")
        assert "|" not in result

    def test_strips_ampersand(self):
        result = sanitize_cli_input("subghz rx 433920000 & rm -rf /")
        assert "&" not in result

    def test_strips_backtick(self):
        result = sanitize_cli_input("ir tx NEC `whoami` 08")
        assert "`" not in result

    def test_strips_dollar_paren(self):
        result = sanitize_cli_input("led r $(reboot)")
        assert "$" not in result
        assert "(" not in result
        assert ")" not in result

    def test_empty_after_sanitize_raises(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_cli_input(";;&||")

    def test_max_length_enforced(self):
        long_cmd = "a" * 600
        with pytest.raises(ValueError, match="exceeds"):
            sanitize_cli_input(long_cmd)

    def test_whitespace_stripped(self):
        assert sanitize_cli_input("  led r 255  ") == "led r 255"


class TestSanitizeArgsForLog:
    def test_redacts_keys(self):
        result = sanitize_args_for_log({"api_key": "sk-secret123"})
        assert result["api_key"] == "[REDACTED]"

    def test_truncates_long_values(self):
        result = sanitize_args_for_log({"content": "x" * 300})
        assert len(result["content"]) < 210
        assert result["content"].endswith("...")

    def test_passes_normal_values(self):
        result = sanitize_args_for_log({"pin": "PA7", "value": 1})
        assert result == {"pin": "PA7", "value": 1}
