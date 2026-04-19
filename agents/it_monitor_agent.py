"""
agents/it_monitor_agent.py
Monitors IT infrastructure: CPU, memory, server uptime.
In production, replace the simulated data with real API/SSH calls.
"""

import random
from typing import Optional
from .base_agent import BaseAgent, Anomaly, AgentStatus, Severity


# ── Simulated server data (replace with real SSH/API calls in prod) ──────────
SIMULATED_SERVERS = [
    {"name": "web-server-01", "cpu": 0.45, "uptime": True},
    {"name": "db-server-01",  "cpu": 0.88, "uptime": True},   # High CPU
    {"name": "api-server-01", "cpu": 0.20, "uptime": False},  # Server down
]

# Thresholds
CPU_THRESHOLD = 0.80      # 80% CPU usage → anomaly
UPTIME_REQUIRED = True    # server must be up


class ITMonitorAgent(BaseAgent):
    """
    Polls infrastructure metrics and detects:
    - Server outages  (uptime = False)
    - High CPU usage  (cpu > CPU_THRESHOLD)
    """

    def __init__(self, agent_id: str = "it_monitor", server_list: list = None,
                 poll_interval: int = 30):
        super().__init__(agent_id)
        self.server_list = server_list or SIMULATED_SERVERS
        self.poll_interval = poll_interval   # seconds between polls

    def _fetch_metrics(self) -> list[dict]:
        """
        Fetch real-time server metrics.
        TODO: Replace with actual SSH checks or monitoring API (Datadog, Prometheus).
        For now, adds slight randomness to simulate live data.
        """
        metrics = []
        for server in self.server_list:
            metrics.append({
                "name": server["name"],
                "cpu": min(1.0, server["cpu"] + random.uniform(-0.05, 0.05)),
                "uptime": server["uptime"],
            })
        return metrics

    def check_cpu(self, server: dict) -> float:
        """Return CPU usage for a server (0.0 – 1.0)."""
        return server.get("cpu", 0.0)

    def check_uptime(self, server: dict) -> bool:
        """Return True if server is up."""
        return server.get("uptime", True)

    def detect_anomaly(self, data: dict) -> Optional[Anomaly]:
        """
        Apply threshold rules to a single server's metrics.
        Returns the most severe anomaly found, or None.
        """
        # Priority 1: Server is completely down
        if not self.check_uptime(data):
            return Anomaly(
                anomaly_id=self._make_id(),
                agent_id=self.agent_id,
                anomaly_type="server_down",
                description=f"Server '{data['name']}' is unreachable.",
                severity=Severity.CRITICAL,
                metadata={"server": data["name"]},
            )

        # Priority 2: High CPU
        cpu = self.check_cpu(data)
        if cpu > CPU_THRESHOLD:
            severity = Severity.HIGH if cpu < 0.95 else Severity.CRITICAL
            return Anomaly(
                anomaly_id=self._make_id(),
                agent_id=self.agent_id,
                anomaly_type="high_cpu",
                description=(f"Server '{data['name']}' CPU at "
                             f"{cpu*100:.1f}% (threshold: {CPU_THRESHOLD*100:.0f}%)"),
                severity=severity,
                metadata={"server": data["name"], "cpu_usage": cpu},
            )

        return None

    def monitor(self) -> Optional[Anomaly]:
        """
        Main monitoring loop step.
        Fetches metrics for all servers and returns the first anomaly found.
        """
        self.status = AgentStatus.MONITORING
        metrics = self._fetch_metrics()

        for server_data in metrics:
            anomaly = self.detect_anomaly(server_data)
            if anomaly:
                self.status = AgentStatus.ANOMALY_DETECTED
                self.report(anomaly)
                return anomaly

        self.status = AgentStatus.IDLE
        print(f"[{self.agent_id}] All systems nominal.")
        return None
