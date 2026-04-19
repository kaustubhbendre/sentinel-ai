"""
agents/base_agent.py
Abstract base class for all Sentinel-AI agents.
Every specialist agent (IT, Business) inherits from this.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AgentStatus(Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    ANOMALY_DETECTED = "anomaly_detected"
    ERROR = "error"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """Represents a detected anomaly from any agent."""
    anomaly_id: str
    agent_id: str
    anomaly_type: str          # e.g. "server_down", "shipping_delay"
    description: str
    severity: Severity
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "anomaly_id": self.anomaly_id,
            "agent_id": self.agent_id,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "resolved": self.resolved,
        }


class BaseAgent(ABC):
    """
    Abstract base for all Sentinel-AI monitoring agents.
    Subclasses must implement: monitor() and detect_anomaly()
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.status = AgentStatus.IDLE
        self._anomaly_count = 0

    @abstractmethod
    def monitor(self) -> Optional[Anomaly]:
        """
        Poll data source and return an Anomaly if one is found,
        otherwise return None.
        """
        pass

    @abstractmethod
    def detect_anomaly(self, data: dict) -> Optional[Anomaly]:
        """
        Given raw data, apply detection logic.
        Returns Anomaly if threshold breached, else None.
        """
        pass

    def report(self, anomaly: Anomaly) -> None:
        """Log anomaly to console (Orchestrator picks it up separately)."""
        print(f"[{self.agent_id}] ANOMALY REPORTED: {anomaly.anomaly_type} "
              f"| Severity: {anomaly.severity.value} "
              f"| {anomaly.description}")
        self._anomaly_count += 1

    def get_status(self) -> AgentStatus:
        return self.status

    def _make_id(self) -> str:
        """Generate a simple unique ID for an anomaly."""
        return f"{self.agent_id}_{self._anomaly_count}_{int(datetime.now().timestamp())}"
