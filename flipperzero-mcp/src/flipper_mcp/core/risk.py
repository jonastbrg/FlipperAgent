"""Risk classification for Flipper Zero MCP tools."""
from enum import Enum
from typing import Dict


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


# Shared severity ordering for vuln triage + reporting
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SEVERITY_LABELS = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "info": "INFO"}
SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}


# Static lookup table — <1ms classification
# Tools not in this table default to MEDIUM
TOOL_RISK_MAP: Dict[str, RiskLevel] = {
    # LOW — read-only, no RF emission, no state change
    "flipper_connection_health": RiskLevel.LOW,
    "flipper_connection_reconnect": RiskLevel.LOW,
    "systeminfo_get": RiskLevel.LOW,
    "badusb_list": RiskLevel.LOW,
    "badusb_read": RiskLevel.LOW,
    "badusb_validate": RiskLevel.LOW,
    "badusb_diff": RiskLevel.LOW,
    "music_get_format": RiskLevel.LOW,
    "subghz_rx": RiskLevel.LOW,
    "subghz_decode_raw": RiskLevel.LOW,
    "ir_rx": RiskLevel.LOW,
    "nfc_detect": RiskLevel.LOW,
    "nfc_field": RiskLevel.LOW,
    "rfid_read": RiskLevel.LOW,
    "gpio_read": RiskLevel.LOW,
    "led_set": RiskLevel.LOW,
    "vibro_set": RiskLevel.LOW,
    "apps_list": RiskLevel.LOW,
    "storage_list": RiskLevel.LOW,
    "storage_read": RiskLevel.LOW,
    "storage_info": RiskLevel.LOW,
    "storage_mkdir": RiskLevel.LOW,
    "audit_query": RiskLevel.LOW,
    # MEDIUM — state changes, limited-range output
    "ir_tx": RiskLevel.MEDIUM,
    "ir_tx_raw": RiskLevel.MEDIUM,
    "gpio_set": RiskLevel.MEDIUM,
    "gpio_mode": RiskLevel.MEDIUM,
    "storage_write": RiskLevel.MEDIUM,
    "storage_delete": RiskLevel.MEDIUM,
    "apps_launch": RiskLevel.MEDIUM,
    "badusb_generate": RiskLevel.MEDIUM,
    "badusb_write": RiskLevel.MEDIUM,
    "badusb_rename": RiskLevel.MEDIUM,
    "music_play": RiskLevel.MEDIUM,
    # HIGH — RF transmission, tag emulation/writing, HID injection
    "subghz_tx": RiskLevel.HIGH,
    "subghz_tx_from_file": RiskLevel.HIGH,
    "nfc_emulate": RiskLevel.HIGH,
    "rfid_emulate": RiskLevel.HIGH,
    "rfid_write": RiskLevel.HIGH,
    "badusb_execute": RiskLevel.HIGH,
    "badusb_workflow": RiskLevel.HIGH,
    # BLE recon via laptop Bluetooth (Bleak)
    "ble_scan": RiskLevel.LOW,
    "ble_enumerate": RiskLevel.MEDIUM,
    "ble_read_char": RiskLevel.MEDIUM,
    "ble_write_char": RiskLevel.HIGH,
    "ble_subscribe": RiskLevel.MEDIUM,
    # ESP32 Marauder WiFi — serial connection, independent of Flipper
    "marauder_scan_ap": RiskLevel.MEDIUM,
    "marauder_scan_sta": RiskLevel.MEDIUM,
    "marauder_list": RiskLevel.LOW,
    "marauder_select": RiskLevel.LOW,
    "marauder_sniff_pmkid": RiskLevel.MEDIUM,
    "marauder_sniff_beacon": RiskLevel.MEDIUM,
    "marauder_sniff_deauth": RiskLevel.MEDIUM,
    "marauder_sniff_raw": RiskLevel.MEDIUM,
    "marauder_deauth": RiskLevel.HIGH,
    "marauder_beacon_spam": RiskLevel.HIGH,
    "marauder_probe_flood": RiskLevel.HIGH,
    "marauder_evil_portal": RiskLevel.HIGH,
    "marauder_karma": RiskLevel.HIGH,
    "marauder_stop": RiskLevel.LOW,
    "marauder_channel": RiskLevel.LOW,
    "marauder_raw_command": RiskLevel.HIGH,
    "marauder_script": RiskLevel.MEDIUM,
    "marauder_exec": RiskLevel.HIGH,
    "marauder_list_scripts": RiskLevel.LOW,
    "marauder_list_pcaps": RiskLevel.LOW,
    "marauder_read_log": RiskLevel.LOW,
    # Vulnerability triage — data management, no active exploitation
    "vuln_submit": RiskLevel.LOW,
    "vuln_validate": RiskLevel.MEDIUM,
    "vuln_list": RiskLevel.LOW,
    "vuln_classify": RiskLevel.LOW,
}

# Blocked path prefixes — use "/int/" not "/int" to avoid matching
# legitimate paths like "/internal_docs/".
_BLOCKED_PREFIXES = ["/int/"]
_BLOCKED_SUFFIXES = [".key", ".priv", ".secret"]


def classify_tool(tool_name: str) -> RiskLevel:
    """Classify a tool by risk level. Unknown tools default to MEDIUM."""
    return TOOL_RISK_MAP.get(tool_name, RiskLevel.MEDIUM)


def is_path_blocked(path: str) -> bool:
    """Check if a file path is blocked (protected system paths)."""
    if not path:
        return False
    p = path.rstrip("/")
    if p == "/int":
        return True
    return (
        any(path.startswith(prefix) for prefix in _BLOCKED_PREFIXES)
        or any(path.endswith(suffix) for suffix in _BLOCKED_SUFFIXES)
    )


def validate_flipper_path(path: str) -> str:
    """Validate a Flipper file path is safe. Returns cleaned path or raises ValueError."""
    if not path:
        raise ValueError("Path is empty")
    if ".." in path:
        raise ValueError("Path traversal ('..') not allowed")
    if is_path_blocked(path):
        raise ValueError(f"Path '{path}' is blocked (protected system path)")
    if not path.startswith("/ext/") and not path.startswith("/ext"):
        raise ValueError(f"Path must be on SD card (/ext/), got: {path}")
    return path
