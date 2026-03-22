"""Audit logging for Flipper Zero MCP tool calls."""
import json
import os
import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from .risk import RiskLevel
from .sanitize import sanitize_args_for_log


@dataclass
class AuditEntry:
    """Single audit log entry for a tool call."""
    timestamp: str
    session_id: str
    tool_name: str
    arguments: Dict
    risk_level: str
    result_summary: str
    duration_ms: float
    success: bool


class AuditLogger:
    """
    Audit logger for Flipper MCP tool calls.

    Maintains an in-memory ring buffer of recent entries and optionally
    writes to a JSONL file specified by the FLIPPER_AUDIT_LOG env var.

    Thread-safe for concurrent tool calls.
    """

    MAX_ENTRIES = 1000

    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())
        self._buffer: Deque[AuditEntry] = deque(maxlen=self.MAX_ENTRIES)
        self._lock = threading.Lock()

        # Optional JSONL file output
        self._log_path: Optional[str] = os.environ.get("FLIPPER_AUDIT_LOG")
        self._file_handle = None
        if self._log_path:
            try:
                self._file_handle = open(self._log_path, "a", encoding="utf-8")
            except OSError as e:
                import sys
                print(
                    f"Warning: Could not open audit log {self._log_path}: {e}",
                    file=sys.stderr,
                )
                self._file_handle = None

    def log_call(
        self,
        tool_name: str,
        arguments: dict,
        risk_level: RiskLevel,
        result: str,
        duration_ms: float,
        success: bool,
    ) -> AuditEntry:
        """
        Log a tool call.

        Args:
            tool_name: Name of the tool that was called
            arguments: Raw arguments dict (will be sanitized)
            risk_level: Risk classification of the tool
            result: Raw result string (will be truncated to 200 chars)
            duration_ms: Execution duration in milliseconds
            success: Whether the call succeeded

        Returns:
            The created AuditEntry
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=self.session_id,
            tool_name=tool_name,
            arguments=sanitize_args_for_log(arguments),
            risk_level=risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level),
            result_summary=result[:200] if result else "",
            duration_ms=round(duration_ms, 2),
            success=success,
        )

        with self._lock:
            self._buffer.append(entry)
            if self._file_handle:
                try:
                    self._file_handle.write(json.dumps(asdict(entry)) + "\n")
                    self._file_handle.flush()
                except OSError:
                    pass  # Best-effort logging; don't break tool calls

        return entry

    def get_log(
        self,
        limit: int = 50,
        tool_name: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        since: Optional[str] = None,
    ) -> List[Dict]:
        """
        Query the audit log.

        Args:
            limit: Maximum number of entries to return
            tool_name: Filter by tool name
            risk_level: Filter by risk level
            since: ISO 8601 timestamp; only return entries after this time

        Returns:
            List of audit entry dicts, most recent first
        """
        with self._lock:
            entries = list(self._buffer)

        # Apply filters
        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]
        if risk_level:
            level_str = risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
            entries = [e for e in entries if e.risk_level == level_str]
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        # Most recent first, limited
        entries = list(reversed(entries))[:limit]
        return [asdict(e) for e in entries]

    def close(self) -> None:
        """Close the JSONL file handle if open."""
        with self._lock:
            if self._file_handle:
                try:
                    self._file_handle.close()
                except OSError:
                    pass
                self._file_handle = None
