"""
agents/biz_monitor_agent.py
Monitors business workflows: order delays, SLA breaches, customer complaints.
In production, connect to your CRM / ERP / order management API.
"""

import random
from typing import Optional
from .base_agent import BaseAgent, Anomaly, AgentStatus, Severity


# ── Simulated CRM / order data ────────────────────────────────────────────────
SIMULATED_ORDERS = [
    {"order_id": "ORD-001", "customer": "Priya Sharma",   "delay_hours": 2,  "status": "on_time"},
    {"order_id": "ORD-002", "customer": "Rahul Mehta",    "delay_hours": 28, "status": "delayed"},
    {"order_id": "ORD-003", "customer": "Anjali Verma",   "delay_hours": 0,  "status": "on_time"},
    {"order_id": "ORD-004", "customer": "Vikram Nair",    "delay_hours": 72, "status": "critical_delay"},
]

# Thresholds
DELAY_MEDIUM_HOURS = 24    # > 24 hrs delay → MEDIUM anomaly
DELAY_HIGH_HOURS   = 48    # > 48 hrs delay → HIGH anomaly
SLA_BREACH_HOURS   = 72    # > 72 hrs delay → CRITICAL (SLA breach)


class BizMonitorAgent(BaseAgent):
    """
    Polls business data and detects:
    - Shipping / order delays
    - SLA breaches
    """

    def __init__(self, agent_id: str = "biz_monitor",
                 crm_endpoint: str = "http://crm.internal/api",
                 sla_threshold: float = 72.0):
        super().__init__(agent_id)
        self.crm_endpoint = crm_endpoint
        self.sla_threshold = sla_threshold

    def _fetch_orders(self) -> list[dict]:
        """
        Fetch orders from CRM.
        TODO: Replace with real HTTP call to your CRM/ERP API.
        """
        orders = []
        for order in SIMULATED_ORDERS:
            jitter = random.uniform(-1, 1)
            orders.append({**order, "delay_hours": max(0, order["delay_hours"] + jitter)})
        return orders

    def check_orders(self) -> list[dict]:
        """Return the full list of current orders."""
        return self._fetch_orders()

    def check_sla_breach(self, order: dict) -> bool:
        """Return True if this order has breached SLA."""
        return order.get("delay_hours", 0) >= self.sla_threshold

    def detect_anomaly(self, data: dict) -> Optional[Anomaly]:
        """
        Classify delay severity for a single order.
        """
        delay = data.get("delay_hours", 0)

        if delay >= SLA_BREACH_HOURS:
            return Anomaly(
                anomaly_id=self._make_id(),
                agent_id=self.agent_id,
                anomaly_type="sla_breach",
                description=(f"Order {data['order_id']} for {data['customer']} "
                             f"is {delay:.0f} hrs delayed — SLA breached."),
                severity=Severity.CRITICAL,
                metadata={"order_id": data["order_id"],
                          "customer": data["customer"],
                          "delay_hours": delay},
            )
        elif delay >= DELAY_HIGH_HOURS:
            return Anomaly(
                anomaly_id=self._make_id(),
                agent_id=self.agent_id,
                anomaly_type="shipping_delay",
                description=(f"Order {data['order_id']} for {data['customer']} "
                             f"is {delay:.0f} hrs late."),
                severity=Severity.HIGH,
                metadata={"order_id": data["order_id"],
                          "customer": data["customer"],
                          "delay_hours": delay},
            )
        elif delay >= DELAY_MEDIUM_HOURS:
            return Anomaly(
                anomaly_id=self._make_id(),
                agent_id=self.agent_id,
                anomaly_type="shipping_delay",
                description=(f"Order {data['order_id']} for {data['customer']} "
                             f"is {delay:.0f} hrs late."),
                severity=Severity.MEDIUM,
                metadata={"order_id": data["order_id"],
                          "customer": data["customer"],
                          "delay_hours": delay},
            )
        return None

    def detect_delay(self) -> Optional[Anomaly]:
        """Convenience method: return first delay anomaly found."""
        for order in self._fetch_orders():
            anomaly = self.detect_anomaly(order)
            if anomaly:
                return anomaly
        return None

    def monitor(self) -> Optional[Anomaly]:
        """
        Main monitoring loop step.
        Returns the most severe order anomaly found.
        """
        self.status = AgentStatus.MONITORING
        orders = self._fetch_orders()
        worst: Optional[Anomaly] = None

        for order in orders:
            anomaly = self.detect_anomaly(order)
            if anomaly:
                if worst is None or anomaly.severity.value > worst.severity.value:
                    worst = anomaly

        if worst:
            self.status = AgentStatus.ANOMALY_DETECTED
            self.report(worst)
            return worst

        self.status = AgentStatus.IDLE
        print(f"[{self.agent_id}] All orders within SLA.")
        return None
