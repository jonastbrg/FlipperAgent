"""Vulnerability triage module for FlipperAgent MCP.

Implements ARTEMIS-style 3-phase triage to reduce false positives:
  1. Submit — log a discovered vulnerability with evidence
  2. Validate — re-test to confirm/reject
  3. Classify — auto-classify severity based on vulnerability type

Stores findings in findings/vulnerabilities.json alongside the project root.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mcp.types import Tool, TextContent

from ..base_module import FlipperModule
from ...core.risk import RiskLevel


# Severity auto-classification rules keyed by vulnerability type keywords
_SEVERITY_RULES: Dict[str, str] = {
    "default_creds": "critical",
    "default_credentials": "critical",
    "default_password": "critical",
    "hardcoded_password": "critical",
    "no_auth": "critical",
    "unauthenticated": "critical",
    "rce": "critical",
    "remote_code_execution": "critical",
    "command_injection": "critical",
    "writable_ble": "high",
    "writable_characteristic": "high",
    "open_admin_port": "high",
    "admin_panel_exposed": "high",
    "ssh_open": "high",
    "telnet_open": "high",
    "unencrypted_protocol": "high",
    "weak_encryption": "high",
    "directory_traversal": "high",
    "sqli": "high",
    "sql_injection": "high",
    "xss": "medium",
    "csrf": "medium",
    "open_port": "medium",
    "outdated_firmware": "medium",
    "outdated_software": "medium",
    "info_disclosure": "low",
    "information_disclosure": "low",
    "version_leak": "low",
    "banner_grab": "low",
    "dns_leak": "low",
}

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_STATUSES = {"submitted", "confirmed", "rejected", "false_positive"}


def _findings_path() -> Path:
    """Return the path to the vulnerability findings JSON file."""
    # Store relative to the project root (two levels up from this file,
    # then into findings/)
    project_root = Path(__file__).resolve().parents[4]
    findings_dir = project_root / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    return findings_dir / "vulnerabilities.json"


import threading

_vulns_lock = threading.Lock()


def _load_vulns() -> List[Dict[str, Any]]:
    """Load vulnerabilities from disk (thread-safe)."""
    path = _findings_path()
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_vulns(vulns: List[Dict[str, Any]]) -> None:
    """Persist vulnerabilities to disk (atomic write + lock)."""
    path = _findings_path()
    tmp = path.with_suffix(".tmp")
    with _vulns_lock:
        with open(tmp, "w") as f:
            json.dump(vulns, f, indent=2, default=str)
        tmp.rename(path)


class VulnTriageModule(FlipperModule):
    """ARTEMIS-style vulnerability triage: submit, validate, classify, list."""

    @property
    def name(self) -> str:
        return "vuln_triage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Vulnerability triage: submit findings, validate with re-testing, "
            "auto-classify severity, list/filter results"
        )

    def get_risk_levels(self) -> Dict[str, RiskLevel]:
        return {
            "vuln_submit": RiskLevel.LOW,
            "vuln_validate": RiskLevel.MEDIUM,
            "vuln_list": RiskLevel.LOW,
            "vuln_classify": RiskLevel.LOW,
        }

    def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="vuln_submit",
                description=(
                    "Submit a discovered vulnerability with target, type, description, "
                    "evidence (raw output), severity, and complexity. "
                    "Returns the assigned vulnerability ID."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Target identifier — IP address, MAC address, or device name",
                        },
                        "vuln_type": {
                            "type": "string",
                            "description": (
                                "Vulnerability type (e.g., default_creds, writable_ble, "
                                "open_admin_port, info_disclosure, rce, xss, sqli)"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description of the vulnerability",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Raw evidence output (tool output, response body, etc.)",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Assessed severity: critical, high, medium, or low",
                        },
                        "complexity": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Exploitation complexity (1 = trivial, 10 = expert-level)",
                        },
                    },
                    "required": ["target", "vuln_type", "description", "evidence", "severity", "complexity"],
                },
            ),
            Tool(
                name="vuln_validate",
                description=(
                    "Validate a previously submitted vulnerability by its ID. "
                    "Marks the finding as confirmed, rejected, or false_positive "
                    "based on reproduction attempt results."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vuln_id": {
                            "type": "string",
                            "description": "Vulnerability UUID (from vuln_submit)",
                        },
                        "reproduced": {
                            "type": "boolean",
                            "description": "Whether the vulnerability was successfully reproduced",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Validation notes (what was tried, what happened)",
                        },
                    },
                    "required": ["vuln_id", "reproduced"],
                },
            ),
            Tool(
                name="vuln_list",
                description=(
                    "List all submitted vulnerabilities with their validation status. "
                    "Optionally filter by target, severity, or status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Filter by target (substring match). Optional.",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Filter by severity. Optional.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["submitted", "confirmed", "rejected", "false_positive"],
                            "description": "Filter by validation status. Optional.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="vuln_classify",
                description=(
                    "Auto-classify severity for a vulnerability based on its type. "
                    "Uses ARTEMIS-style rules: default_creds=CRITICAL, writable BLE=HIGH, "
                    "open admin ports=HIGH, info disclosure=LOW, etc. "
                    "Can also reclassify an existing finding by vuln_id."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vuln_type": {
                            "type": "string",
                            "description": (
                                "Vulnerability type to classify (e.g., default_creds, "
                                "writable_ble, open_admin_port)"
                            ),
                        },
                        "vuln_id": {
                            "type": "string",
                            "description": (
                                "Optional: if provided, update this existing finding's "
                                "severity to the auto-classified value"
                            ),
                        },
                    },
                    "required": ["vuln_type"],
                },
            ),
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        return await self._dispatch(tool_name, arguments, {
            "vuln_submit": self._submit,
            "vuln_validate": self._validate,
            "vuln_list": self._list,
            "vuln_classify": self._classify,
        }, "Vuln triage error")

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _submit(self, args: dict) -> Sequence[TextContent]:
        severity = args["severity"].lower()
        if severity not in VALID_SEVERITIES:
            return [TextContent(
                type="text",
                text=f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}",
            )]

        complexity = args["complexity"]
        if not (1 <= complexity <= 10):
            return [TextContent(type="text", text="Complexity must be between 1 and 10")]

        vuln_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        vuln = {
            "id": vuln_id,
            "target": args["target"],
            "vuln_type": args["vuln_type"],
            "description": args["description"],
            "evidence": args["evidence"],
            "severity": severity,
            "complexity": complexity,
            "status": "submitted",
            "submitted_at": now,
            "validated_at": None,
            "reproduction_attempts": 0,
            "validation_notes": [],
        }

        vulns = _load_vulns()
        vulns.append(vuln)
        _save_vulns(vulns)

        return [TextContent(
            type="text",
            text=(
                f"Vulnerability submitted: {vuln_id}\n"
                f"  Target: {args['target']}\n"
                f"  Type: {args['vuln_type']}\n"
                f"  Severity: {severity.upper()}\n"
                f"  Complexity: {complexity}/10\n"
                f"  Status: submitted\n"
                f"  Stored in: {_findings_path()}"
            ),
        )]

    async def _validate(self, args: dict) -> Sequence[TextContent]:
        vuln_id = args["vuln_id"]
        reproduced = args["reproduced"]
        notes = args.get("notes", "")

        vulns = _load_vulns()
        vuln = next((v for v in vulns if v["id"] == vuln_id), None)
        if not vuln:
            return [TextContent(type="text", text=f"Vulnerability {vuln_id} not found")]

        now = datetime.now(timezone.utc).isoformat()
        vuln["reproduction_attempts"] = vuln.get("reproduction_attempts", 0) + 1
        vuln["validated_at"] = now

        if reproduced:
            vuln["status"] = "confirmed"
        else:
            # On first failed reproduction, mark as rejected.
            # If it was already confirmed and this is a re-test, mark false_positive.
            if vuln["status"] == "confirmed":
                vuln["status"] = "false_positive"
            else:
                vuln["status"] = "rejected"

        if notes:
            if "validation_notes" not in vuln:
                vuln["validation_notes"] = []
            vuln["validation_notes"].append({
                "timestamp": now,
                "reproduced": reproduced,
                "notes": notes,
            })

        _save_vulns(vulns)

        return [TextContent(
            type="text",
            text=(
                f"Vulnerability {vuln_id} validated:\n"
                f"  Status: {vuln['status'].upper()}\n"
                f"  Reproduced: {reproduced}\n"
                f"  Attempts: {vuln['reproduction_attempts']}\n"
                f"  Notes: {notes or '(none)'}"
            ),
        )]

    async def _list(self, args: dict) -> Sequence[TextContent]:
        vulns = _load_vulns()

        # Apply filters
        target_filter = args.get("target", "").lower()
        severity_filter = args.get("severity", "").lower()
        status_filter = args.get("status", "").lower()

        if target_filter:
            vulns = [v for v in vulns if target_filter in v.get("target", "").lower()]
        if severity_filter:
            vulns = [v for v in vulns if v.get("severity", "").lower() == severity_filter]
        if status_filter:
            vulns = [v for v in vulns if v.get("status", "").lower() == status_filter]

        if not vulns:
            return [TextContent(type="text", text="No vulnerabilities found matching filters.")]

        # Summary stats
        by_severity = {}
        by_status = {}
        for v in vulns:
            sev = v.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            st = v.get("status", "unknown")
            by_status[st] = by_status.get(st, 0) + 1

        lines = [
            f"Vulnerabilities: {len(vulns)} total",
            f"  By severity: {', '.join(f'{k.upper()}={v}' for k, v in sorted(by_severity.items()))}",
            f"  By status: {', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))}",
            "",
        ]

        # Sort: critical first, then high, medium, low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        vulns.sort(key=lambda v: severity_order.get(v.get("severity", "low"), 4))

        for v in vulns:
            status_icon = {
                "submitted": "[?]",
                "confirmed": "[!]",
                "rejected": "[x]",
                "false_positive": "[-]",
            }.get(v.get("status", ""), "[?]")

            lines.append(
                f"  {status_icon} {v['id']} | {v.get('severity', '?').upper()} | "
                f"{v.get('target', '?')} | {v.get('vuln_type', '?')} | "
                f"status={v.get('status', '?')} | complexity={v.get('complexity', '?')}/10"
            )
            lines.append(f"      {v.get('description', '')[:120]}")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _classify(self, args: dict) -> Sequence[TextContent]:
        vuln_type = args["vuln_type"].lower().strip()
        vuln_id = args.get("vuln_id")

        # Look up in rules — try exact match first, then substring
        classified = _SEVERITY_RULES.get(vuln_type)
        if not classified:
            # Try matching as substring
            for rule_key, rule_sev in _SEVERITY_RULES.items():
                if rule_key in vuln_type or vuln_type in rule_key:
                    classified = rule_sev
                    break

        if not classified:
            classified = "medium"  # Default if no rule matches

        result_lines = [
            f"Auto-classification: {vuln_type} -> {classified.upper()}",
        ]

        # If vuln_id provided, update the existing finding
        if vuln_id:
            vulns = _load_vulns()
            vuln = next((v for v in vulns if v["id"] == vuln_id), None)
            if vuln:
                old_severity = vuln.get("severity", "unknown")
                vuln["severity"] = classified
                _save_vulns(vulns)
                result_lines.append(
                    f"  Updated {vuln_id}: {old_severity.upper()} -> {classified.upper()}"
                )
            else:
                result_lines.append(f"  Warning: vuln_id {vuln_id} not found, classification not applied")

        # Show the rule that matched
        result_lines.append("")
        result_lines.append("Classification rules reference:")
        result_lines.append("  CRITICAL: default_creds, no_auth, rce, command_injection, hardcoded_password")
        result_lines.append("  HIGH: writable_ble, open_admin_port, ssh/telnet_open, sqli, directory_traversal")
        result_lines.append("  MEDIUM: xss, csrf, open_port, outdated_firmware/software")
        result_lines.append("  LOW: info_disclosure, version_leak, banner_grab, dns_leak")

        return [TextContent(type="text", text="\n".join(result_lines))]
