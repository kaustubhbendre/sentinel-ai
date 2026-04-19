"""
tests/test_sentinel.py
Unit + Integration tests for Sentinel-AI.
Run with: pytest tests/ -v
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import Anomaly, Severity, AgentStatus
from agents.it_monitor_agent import ITMonitorAgent, CPU_THRESHOLD
from agents.biz_monitor_agent import BizMonitorAgent, DELAY_HIGH_HOURS, SLA_BREACH_HOURS
from rag.rag_engine import RAGEngine, LOCAL_KNOWLEDGE_BASE
from actions.action_engine import ActionEngine, ActionResult
from utils.incident_log import IncidentLog, IncidentStatus


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — ITMonitorAgent
# ══════════════════════════════════════════════════════════════════

class TestITMonitorAgent:

    def setup_method(self):
        self.agent = ITMonitorAgent(agent_id="test_it_agent")

    def test_agent_initialises_correctly(self):
        assert self.agent.agent_id == "test_it_agent"
        assert self.agent.status == AgentStatus.IDLE

    def test_detects_server_down(self):
        data = {"name": "web-01", "cpu": 0.3, "uptime": False}
        anomaly = self.agent.detect_anomaly(data)
        assert anomaly is not None
        assert anomaly.anomaly_type == "server_down"
        assert anomaly.severity == Severity.CRITICAL

    def test_detects_high_cpu(self):
        data = {"name": "db-01", "cpu": 0.92, "uptime": True}
        anomaly = self.agent.detect_anomaly(data)
        assert anomaly is not None
        assert anomaly.anomaly_type == "high_cpu"
        assert anomaly.severity in (Severity.HIGH, Severity.CRITICAL)

    def test_no_anomaly_on_healthy_server(self):
        data = {"name": "api-01", "cpu": 0.30, "uptime": True}
        anomaly = self.agent.detect_anomaly(data)
        assert anomaly is None

    def test_server_down_takes_priority_over_high_cpu(self):
        """Even if CPU is high, server_down is more critical."""
        data = {"name": "web-01", "cpu": 0.99, "uptime": False}
        anomaly = self.agent.detect_anomaly(data)
        assert anomaly.anomaly_type == "server_down"

    def test_check_uptime_true(self):
        assert self.agent.check_uptime({"uptime": True}) is True

    def test_check_uptime_false(self):
        assert self.agent.check_uptime({"uptime": False}) is False

    def test_check_cpu_returns_value(self):
        cpu = self.agent.check_cpu({"cpu": 0.75})
        assert cpu == pytest.approx(0.75)


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — BizMonitorAgent
# ══════════════════════════════════════════════════════════════════

class TestBizMonitorAgent:

    def setup_method(self):
        self.agent = BizMonitorAgent(agent_id="test_biz_agent")

    def test_agent_initialises_correctly(self):
        assert self.agent.agent_id == "test_biz_agent"
        assert self.agent.status == AgentStatus.IDLE

    def test_detects_sla_breach(self):
        order = {"order_id": "ORD-X", "customer": "Test User",
                 "delay_hours": 73, "status": "critical_delay"}
        anomaly = self.agent.detect_anomaly(order)
        assert anomaly is not None
        assert anomaly.anomaly_type == "sla_breach"
        assert anomaly.severity == Severity.CRITICAL

    def test_detects_high_delay(self):
        order = {"order_id": "ORD-Y", "customer": "Another User",
                 "delay_hours": 50, "status": "delayed"}
        anomaly = self.agent.detect_anomaly(order)
        assert anomaly is not None
        assert anomaly.anomaly_type == "shipping_delay"
        assert anomaly.severity == Severity.HIGH

    def test_detects_medium_delay(self):
        order = {"order_id": "ORD-Z", "customer": "Third User",
                 "delay_hours": 30, "status": "delayed"}
        anomaly = self.agent.detect_anomaly(order)
        assert anomaly is not None
        assert anomaly.anomaly_type == "shipping_delay"
        assert anomaly.severity == Severity.MEDIUM

    def test_no_anomaly_on_time_order(self):
        order = {"order_id": "ORD-OK", "customer": "Happy User",
                 "delay_hours": 1, "status": "on_time"}
        anomaly = self.agent.detect_anomaly(order)
        assert anomaly is None

    def test_check_sla_breach_true(self):
        order = {"delay_hours": 80}
        assert self.agent.check_sla_breach(order) is True

    def test_check_sla_breach_false(self):
        order = {"delay_hours": 10}
        assert self.agent.check_sla_breach(order) is False


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — RAGEngine
# ══════════════════════════════════════════════════════════════════

class TestRAGEngine:

    def setup_method(self):
        self.rag = RAGEngine()

    def test_returns_context_for_server_down(self):
        ctx = self.rag.get_context("server_down")
        assert len(ctx) > 10
        assert "server" in ctx.lower() or "restart" in ctx.lower()

    def test_returns_context_for_shipping_delay(self):
        ctx = self.rag.get_context("shipping_delay")
        assert len(ctx) > 10

    def test_returns_fallback_for_unknown_type(self):
        ctx = self.rag.get_context("alien_invasion")
        assert "general incident" in ctx.lower() or "no specific" in ctx.lower()

    def test_embed_query_returns_vector(self):
        vec = self.rag.embed_query("server is down")
        assert isinstance(vec, list)
        assert len(vec) == 384


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — ActionEngine
# ══════════════════════════════════════════════════════════════════

class TestActionEngine:

    def setup_method(self):
        self.engine = ActionEngine()

    def test_restart_server_returns_action_result(self):
        result = self.engine.restart_server("test-server-01")
        assert isinstance(result, ActionResult)
        assert result.action_type == "restart_server"
        assert isinstance(result.success, bool)

    def test_send_email_demo_mode_succeeds(self):
        """In demo mode (no real email config), should still return success."""
        # Force demo mode by clearing credentials
        engine = ActionEngine()
        engine._email_sender = ""
        engine._email_password = ""
        result = engine.send_email(
            recipient="test@example.com",
            customer_name="Test Customer",
            order_id="ORD-TEST",
            delay_hours=48,
        )
        assert isinstance(result, ActionResult)
        assert result.action_type == "send_email"
        assert result.success is True

    def test_create_ticket_returns_ticket_id(self):
        result = self.engine.create_ticket(
            title="Test Incident",
            description="This is a test",
            priority="high",
        )
        assert result.success is True
        assert "TKT-" in result.details.get("ticket_id", "")


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — IncidentLog
# ══════════════════════════════════════════════════════════════════

class TestIncidentLog:

    def _make_anomaly(self):
        return Anomaly(
            anomaly_id="test-123",
            agent_id="it_monitor",
            anomaly_type="server_down",
            description="Test server is down.",
            severity=Severity.CRITICAL,
            metadata={"server": "test-server"},
        )

    def test_create_from_anomaly(self):
        anomaly = self._make_anomaly()
        log = IncidentLog.create(anomaly, llm_reasoning="Restart the server.")
        assert log.anomaly_type == "server_down"
        assert log.severity == "critical"
        assert log.status == IncidentStatus.OPEN
        assert "Restart" in log.llm_reasoning

    def test_update_status_to_resolved(self):
        log = IncidentLog.create(self._make_anomaly())
        log.update_status(IncidentStatus.RESOLVED, "Server restarted successfully.")
        assert log.status == IncidentStatus.RESOLVED
        assert log.resolved_at is not None
        assert len(log.actions_taken) == 1

    def test_to_dict_has_required_keys(self):
        log = IncidentLog.create(self._make_anomaly())
        d = log.to_dict()
        for key in ["incident_id", "anomaly_type", "severity", "status",
                    "created_at", "actions_taken", "llm_reasoning"]:
            assert key in d, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestIntegration:
    """
    End-to-end pipeline tests without real LLM or email.
    Tests that all components connect correctly.
    """

    def test_server_down_triggers_restart_action(self):
        """Full pipeline: server_down anomaly → RAG → ActionEngine."""
        it_agent = ITMonitorAgent()
        # Force a server_down anomaly
        it_agent.server_list = [{"name": "prod-01", "cpu": 0.2, "uptime": False}]
        anomaly = it_agent.monitor()

        assert anomaly is not None
        assert anomaly.anomaly_type == "server_down"

        rag = RAGEngine()
        context = rag.get_context(anomaly.anomaly_type)
        assert len(context) > 0

        engine = ActionEngine()
        result = engine.restart_server(anomaly.metadata.get("server", "prod-01"))
        assert result.action_type == "restart_server"

    def test_sla_breach_triggers_email(self):
        """Full pipeline: SLA breach → email action."""
        biz_agent = BizMonitorAgent()
        biz_agent.server_list = []  # Not used in biz agent
        # Force an SLA breach order
        biz_agent.server_list = None
        order = {"order_id": "ORD-999", "customer": "Rahul Mehta",
                 "delay_hours": 80, "status": "sla_breach"}
        anomaly = biz_agent.detect_anomaly(order)

        assert anomaly is not None
        assert anomaly.anomaly_type == "sla_breach"

        engine = ActionEngine()
        engine._email_sender = ""
        engine._email_password = ""
        result = engine.send_email(
            recipient="rahul.mehta@email.com",
            customer_name=anomaly.metadata["customer"],
            order_id=anomaly.metadata["order_id"],
            delay_hours=anomaly.metadata["delay_hours"],
        )
        assert result.success is True

    def test_incident_log_full_lifecycle(self):
        """Test create → update → serialise."""
        anomaly = Anomaly(
            anomaly_id="int-001",
            agent_id="biz_monitor",
            anomaly_type="shipping_delay",
            description="Order delayed by 30 hours.",
            severity=Severity.HIGH,
            metadata={"order_id": "ORD-INT", "customer": "Test"},
        )
        log = IncidentLog.create(anomaly, "Send apology email.")
        assert log.status == IncidentStatus.OPEN

        log.update_status(IncidentStatus.RESOLVED, "Apology email sent.")
        assert log.status == IncidentStatus.RESOLVED
        assert len(log.actions_taken) == 1

        d = log.to_dict()
        assert d["status"] == "resolved"
        assert d["actions_taken"][0]["action"] == "Apology email sent."