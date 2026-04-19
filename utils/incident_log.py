"""
utils/incident_log.py
Tracks every incident from detection through resolution.
Persists to data/incidents.jsonl for the dashboard to read.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class IncidentStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class IncidentLog:
    incident_id: str
    anomaly_type: str
    description: str
    severity: str
    agent_id: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    actions_taken: list = field(default_factory=list)
    llm_reasoning: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, anomaly, llm_reasoning: str = "") -> "IncidentLog":
        """Factory: create an IncidentLog from an Anomaly."""
        incident_id = f"INC-{int(datetime.now().timestamp())}"
        return cls(
            incident_id=incident_id,
            anomaly_type=anomaly.anomaly_type,
            description=anomaly.description,
            severity=anomaly.severity.value,
            agent_id=anomaly.agent_id,
            llm_reasoning=llm_reasoning,
            metadata=anomaly.metadata,
        )

    def update_status(self, status: IncidentStatus,
                      action_taken: str = "") -> None:
        self.status = status
        if action_taken:
            self.actions_taken.append({
                "action": action_taken,
                "timestamp": datetime.now().isoformat(),
            })
        if status == IncidentStatus.RESOLVED:
            self.resolved_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "severity": self.severity,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "actions_taken": self.actions_taken,
            "llm_reasoning": self.llm_reasoning,
            "metadata": self.metadata,
        }

    def save(self, path: str = "data/incidents.jsonl") -> None:
        """Append this incident to the JSONL log file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(self.to_dict()) + "\n")
