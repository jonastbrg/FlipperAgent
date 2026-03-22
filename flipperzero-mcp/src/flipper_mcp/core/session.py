"""Session persistence for long-running pentest engagements."""
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class EngagementState:
    """Tracks the state of an autonomous pentest engagement."""
    engagement_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = ""
    phase: str = "recon"  # recon, research, enumerate, exploit, report
    targets_discovered: List[Dict] = field(default_factory=list)
    vulnerabilities: List[Dict] = field(default_factory=list)
    credentials_found: List[Dict] = field(default_factory=list)
    attack_chains: List[Dict] = field(default_factory=list)
    phases_completed: List[str] = field(default_factory=list)
    notes: str = ""  # Free-form agent notes (ARTEMIS supervisor pattern)
    todo_list: List[str] = field(default_factory=list)  # Recursive TODO (ARTEMIS pattern)


class SessionManager:
    """Save and resume engagement state to disk."""

    def __init__(self, base_dir: str = "findings"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base_dir / "engagement_state.json"
        self.state: EngagementState = EngagementState()

    def save(self) -> None:
        """Save current state to disk."""
        with open(self.state_file, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def load(self) -> Optional[EngagementState]:
        """Load state from disk. Returns None if no saved state."""
        if not self.state_file.exists():
            return None
        with open(self.state_file) as f:
            data = json.load(f)
        self.state = EngagementState(**data)
        return self.state

    def new_engagement(self) -> EngagementState:
        """Start a fresh engagement."""
        self.state = EngagementState(
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self.save()
        return self.state

    def advance_phase(self, next_phase: str) -> None:
        """Mark current phase complete and advance."""
        if self.state.phase not in self.state.phases_completed:
            self.state.phases_completed.append(self.state.phase)
        self.state.phase = next_phase
        self.save()

    def add_target(self, target: Dict) -> None:
        self.state.targets_discovered.append(target)
        self.save()

    def update_or_add_target(self, target: Dict) -> None:
        """Add a target, or update an existing one if a target with the same address exists."""
        address = target.get("address")
        if address:
            for i, existing in enumerate(self.state.targets_discovered):
                if existing.get("address") == address:
                    existing.update(target)
                    self.save()
                    return
        self.state.targets_discovered.append(target)
        self.save()

    def add_vulnerability(self, vuln: Dict) -> None:
        self.state.vulnerabilities.append(vuln)
        self.save()

    def add_credential(self, cred: Dict) -> None:
        self.state.credentials_found.append(cred)
        self.save()

    def update_notes(self, notes: str) -> None:
        self.state.notes = notes
        self.save()

    def update_todos(self, todos: List[str]) -> None:
        self.state.todo_list = todos
        self.save()
