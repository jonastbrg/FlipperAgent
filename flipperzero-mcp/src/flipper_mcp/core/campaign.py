"""Campaign management for FlipperAgent.

A Campaign is a sustained, multi-session security assessment against one or
more targets. It extends the Ralph Wiggum loop pattern with:

- Target selection and prioritization
- Expansion tree (pivot from one target to discover more)
- Per-target attack plans with tool selection
- Sub-agent delegation (parallel agents on different vectors)
- Review gates (council/liza before HIGH-risk actions)
- Persistent state across sessions
- Continuous findings accumulation

Hierarchy:
  Campaign → Targets → Attack Plans → Phases → Tool Calls
"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AttackVector:
    """A specific attack approach for a target."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    tools: List[str] = field(default_factory=list)
    status: str = "planned"  # planned, in_progress, succeeded, failed, blocked
    risk_level: str = "MEDIUM"
    findings: List[Dict] = field(default_factory=list)
    attempts: int = 0
    last_attempt: str = ""
    notes: str = ""


@dataclass
class Target:
    """A target device/service under assessment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    type: str = ""  # ble_device, wifi_network, ip_host, rf_device, nfc_tag
    address: str = ""  # BLE MAC, IP, frequency, etc.
    discovered_via: str = ""  # which tool/phase discovered this
    discovered_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)  # RSSI, firmware, manufacturer, etc.
    attack_vectors: List[AttackVector] = field(default_factory=list)
    status: str = "discovered"  # discovered, researching, enumerating, exploiting, compromised, abandoned
    priority: int = 50  # 0=highest, 100=lowest
    children: List[str] = field(default_factory=list)  # target IDs discovered FROM this target (expansion tree)
    parent: Optional[str] = None  # target ID that led to this discovery
    findings_summary: str = ""


@dataclass
class CampaignState:
    """Full state of a security assessment campaign."""
    campaign_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = ""
    status: str = "active"  # active, paused, completed, aborted

    # Scope
    scope_description: str = ""  # "All BLE devices within 30m of desk"
    scope_targets: List[str] = field(default_factory=list)  # allowed target addresses/ranges
    out_of_scope: List[str] = field(default_factory=list)  # explicitly excluded

    # Targets (the expansion tree)
    targets: List[Target] = field(default_factory=list)

    # Campaign-level tracking
    current_phase: str = "recon"  # recon, research, enumerate, exploit, report
    iteration: int = 0
    max_iterations: int = 50
    phases_completed: List[str] = field(default_factory=list)

    # Agent coordination
    active_agents: List[Dict] = field(default_factory=list)  # {agent_id, target_id, vector_id, status}
    review_queue: List[Dict] = field(default_factory=list)  # HIGH-risk actions pending review

    # ARTEMIS-style supervisor notes
    notes: str = ""
    todo_list: List[str] = field(default_factory=list)
    decisions: List[Dict] = field(default_factory=list)  # {timestamp, decision, rationale, reviewed_by}

    # Findings
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0


class CampaignManager:
    """Manage campaign lifecycle and persistence."""

    def __init__(self, campaigns_dir: str = "campaigns"):
        self.base_dir = Path(campaigns_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state: Optional[CampaignState] = None

    def _campaign_dir(self, campaign_id: str) -> Path:
        d = self.base_dir / campaign_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _state_file(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "campaign_state.json"

    def save(self) -> None:
        if not self.state:
            return
        self.state.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = self._state_file(self.state.campaign_id)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)
        tmp.rename(path)

    def load(self, campaign_id: str) -> Optional[CampaignState]:
        path = self._state_file(campaign_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        # Reconstruct nested dataclasses
        targets = []
        for t in data.get("targets", []):
            vectors = [AttackVector(**v) for v in t.pop("attack_vectors", [])]
            targets.append(Target(**t, attack_vectors=vectors))
        data["targets"] = targets
        self.state = CampaignState(**data)
        return self.state

    def list_campaigns(self) -> List[Dict]:
        campaigns = []
        for d in sorted(self.base_dir.iterdir()):
            sf = d / "campaign_state.json"
            if sf.exists():
                try:
                    with open(sf) as f:
                        data = json.load(f)
                    campaigns.append({
                        "id": data["campaign_id"],
                        "name": data.get("name", ""),
                        "status": data.get("status", ""),
                        "targets": len(data.get("targets", [])),
                        "findings": data.get("total_findings", 0),
                        "updated": data.get("updated_at", ""),
                    })
                except Exception:
                    pass
        return campaigns

    def new_campaign(self, name: str, description: str = "", scope: str = "") -> CampaignState:
        self.state = CampaignState(
            name=name,
            description=description,
            scope_description=scope,
        )
        self.save()
        return self.state

    def add_target(self, target: Target) -> None:
        if not self.state:
            raise RuntimeError("No active campaign")
        target.discovered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.state.targets.append(target)
        self.save()

    def get_target(self, target_id: str) -> Optional[Target]:
        if not self.state:
            return None
        for t in self.state.targets:
            if t.id == target_id:
                return t
        return None

    def update_target_status(self, target_id: str, status: str) -> None:
        t = self.get_target(target_id)
        if t:
            t.status = status
            self.save()

    def add_vector(self, target_id: str, vector: AttackVector) -> None:
        t = self.get_target(target_id)
        if t:
            t.attack_vectors.append(vector)
            self.save()

    def add_finding(self, target_id: str, finding: Dict) -> None:
        t = self.get_target(target_id)
        if not t:
            return
        # Find the vector this finding belongs to
        vector_id = finding.get("vector_id")
        if vector_id:
            for v in t.attack_vectors:
                if v.id == vector_id:
                    v.findings.append(finding)
                    break
        # Update campaign-level counts
        severity = finding.get("severity", "medium").lower()
        self.state.total_findings += 1
        if severity == "critical":
            self.state.critical_findings += 1
        elif severity == "high":
            self.state.high_findings += 1
        elif severity == "medium":
            self.state.medium_findings += 1
        else:
            self.state.low_findings += 1
        self.save()

    def add_child_target(self, parent_id: str, child: Target) -> None:
        """Add a target discovered FROM another target (expansion tree)."""
        child.parent = parent_id
        child.discovered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.state.targets.append(child)
        parent = self.get_target(parent_id)
        if parent:
            parent.children.append(child.id)
        self.save()

    def get_expansion_tree(self) -> Dict:
        """Return the target expansion tree as nested dict."""
        if not self.state:
            return {}
        by_id = {t.id: t for t in self.state.targets}
        roots = [t for t in self.state.targets if t.parent is None]

        def build_tree(target: Target) -> Dict:
            node = {
                "id": target.id,
                "name": target.name,
                "type": target.type,
                "status": target.status,
                "vectors": len(target.attack_vectors),
                "findings": sum(len(v.findings) for v in target.attack_vectors),
                "children": [],
            }
            for child_id in target.children:
                child = by_id.get(child_id)
                if child:
                    node["children"].append(build_tree(child))
            return node

        return {"campaign": self.state.name, "trees": [build_tree(r) for r in roots]}

    def get_next_target(self) -> Optional[Target]:
        """Get the highest-priority target that still needs work."""
        if not self.state:
            return None
        active = [t for t in self.state.targets if t.status not in ("compromised", "abandoned")]
        if not active:
            return None
        return min(active, key=lambda t: t.priority)

    def queue_for_review(self, action: Dict) -> None:
        """Queue a HIGH-risk action for council/liza review."""
        action["queued_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        action["status"] = "pending_review"
        self.state.review_queue.append(action)
        self.save()

    def log_decision(self, decision: str, rationale: str, reviewed_by: str = "auto") -> None:
        self.state.decisions.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "decision": decision,
            "rationale": rationale,
            "reviewed_by": reviewed_by,
        })
        self.save()

    def advance_iteration(self) -> bool:
        """Advance campaign iteration. Returns False if max reached."""
        if not self.state:
            return False
        self.state.iteration += 1
        self.save()
        return self.state.iteration < self.state.max_iterations
