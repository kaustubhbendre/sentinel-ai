"""
orchestrator/orchestrator.py
The brain of Sentinel-AI.
Uses LangGraph to coordinate agents, RAG, LLM reasoning, and actions.
"""

import os
from typing import Optional, TypedDict
from dotenv import load_dotenv

from agents import ITMonitorAgent, BizMonitorAgent, Anomaly, Severity
from rag import RAGEngine
from actions import ActionEngine, ActionResult
from utils.incident_log import IncidentLog, IncidentStatus

load_dotenv()


# ── LangGraph State Schema ────────────────────────────────────────────────────
class SentinelState(TypedDict):
    anomaly: Optional[dict]        # Serialised Anomaly
    context: str                   # RAG-retrieved context
    llm_decision: str              # LLM reasoning output
    action_taken: str              # Action name executed
    action_result: Optional[dict]  # ActionResult
    escalate: bool                 # Should human intervene?
    incident_id: str               # Linked IncidentLog ID


class Orchestrator:
    """
    Coordinates the full Sentinel-AI pipeline:
    Monitor → Detect → RAG → LLM → Act → Log → Dashboard
    """

    def __init__(self, agent_id: str = "orchestrator",
                 llm_model: str = "llama3-8b-8192"):
        self.agent_id = agent_id
        self.llm_model = llm_model

        # Initialise sub-systems
        self.it_agent  = ITMonitorAgent()
        self.biz_agent = BizMonitorAgent()
        self.rag       = RAGEngine()
        self.actions   = ActionEngine()
        self._groq_client = None
        self._init_groq()

    def _init_groq(self):
        """Connect to Groq for fast LLM inference."""
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "your_groq_api_key_here":
            print("[Orchestrator] No Groq key — LLM reasoning will use rule-based fallback.")
            return
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=api_key)
            print(f"[Orchestrator] Groq connected. Model: {self.llm_model}")
        except Exception as e:
            print(f"[Orchestrator] Groq init failed: {e}")

    # ── LangGraph Node Functions ──────────────────────────────────────────

    def node_monitor(self, state: SentinelState) -> SentinelState:
        """Node 1: Run both agents, pick first anomaly found."""
        print("\n[Orchestrator] ── Monitoring ──")
        anomaly = self.it_agent.monitor() or self.biz_agent.monitor()
        if anomaly:
            state["anomaly"] = anomaly.to_dict()
            print(f"[Orchestrator] Anomaly detected: {anomaly.anomaly_type}")
        else:
            state["anomaly"] = None
            print("[Orchestrator] No anomalies detected.")
        return state

    def node_retrieve_context(self, state: SentinelState) -> SentinelState:
        """Node 2: Query RAG for relevant runbooks/policies."""
        if not state.get("anomaly"):
            return state
        anomaly_type = state["anomaly"]["anomaly_type"]
        print(f"[Orchestrator] ── RAG lookup: {anomaly_type} ──")
        state["context"] = self.rag.get_context(anomaly_type)
        return state

    def node_llm_reason(self, state: SentinelState) -> SentinelState:
        """Node 3: Ask the LLM what action to take."""
        if not state.get("anomaly"):
            return state
        print("[Orchestrator] ── LLM Reasoning ──")
        state["llm_decision"] = self.reason_with_llm(
            anomaly=state["anomaly"],
            context=state["context"],
        )
        print(f"[Orchestrator] LLM decided: {state['llm_decision'][:120]}...")
        return state

    def node_execute_action(self, state: SentinelState) -> SentinelState:
        """Node 4: Execute the action the LLM recommended."""
        if not state.get("anomaly"):
            return state
        print("[Orchestrator] ── Executing Action ──")
        anomaly = state["anomaly"]
        result = self.dispatch_action(anomaly, state["llm_decision"])
        state["action_result"] = result.to_dict()
        state["action_taken"] = result.action_type
        state["escalate"] = not result.success
        return state

    def node_log_incident(self, state: SentinelState) -> SentinelState:
        """Node 5: Create and persist the IncidentLog."""
        if not state.get("anomaly"):
            return state
        print("[Orchestrator] ── Logging Incident ──")

        # Reconstruct anomaly object minimally for IncidentLog
        from agents.base_agent import Anomaly as AnomalyObj, Severity
        from datetime import datetime
        a = state["anomaly"]
        mock_anomaly = AnomalyObj(
            anomaly_id=a["anomaly_id"],
            agent_id=a["agent_id"],
            anomaly_type=a["anomaly_type"],
            description=a["description"],
            severity=Severity(a["severity"]),
            metadata=a.get("metadata", {}),
        )
        log = IncidentLog.create(mock_anomaly, state.get("llm_decision", ""))
        action_result = state.get("action_result", {})
        status = IncidentStatus.RESOLVED if not state.get("escalate") else IncidentStatus.ESCALATED
        log.update_status(status, action_result.get("message", ""))
        log.save()
        state["incident_id"] = log.incident_id
        print(f"[Orchestrator] Incident saved: {log.incident_id} | {status.value}")
        return state

    # ── Core Methods ──────────────────────────────────────────────────────

    def reason_with_llm(self, anomaly: dict, context: str) -> str:
        """
        Ask the LLM (Llama 3 via Groq) what action to take.
        Falls back to rule-based logic if Groq is unavailable.
        """
        if self._groq_client:
            prompt = (
                f"You are Sentinel-AI, an autonomous IT and business support engine.\n\n"
                f"ANOMALY DETECTED:\n{anomaly['description']}\n"
                f"Severity: {anomaly['severity']}\n\n"
                f"RELEVANT CONTEXT (runbooks/policies):\n{context}\n\n"
                f"Based on the above, state in ONE sentence: "
                f"what single action should be taken RIGHT NOW? "
                f"Be specific and actionable."
            )
            try:
                response = self._groq_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[Orchestrator] LLM call failed: {e}")

        # Rule-based fallback
        return self._rule_based_decision(anomaly["anomaly_type"])

    def dispatch_action(self, anomaly: dict, llm_decision: str) -> ActionResult:
        """
        Route to the correct ActionEngine method based on anomaly type.
        """
        atype = anomaly.get("anomaly_type", "")
        meta  = anomaly.get("metadata", {})

        if atype == "server_down":
            return self.actions.restart_server(meta.get("server", "unknown-server"))

        elif atype == "high_cpu":
            return self.actions.create_ticket(
                title=f"High CPU on {meta.get('server', 'unknown')}",
                description=llm_decision,
                priority="high",
            )

        elif atype in ("shipping_delay", "sla_breach"):
            return self.actions.send_email(
                recipient=f"{meta.get('customer', 'customer').lower().replace(' ', '.')}@email.com",
                customer_name=meta.get("customer", "Valued Customer"),
                order_id=meta.get("order_id", "N/A"),
                delay_hours=meta.get("delay_hours", 0),
                llm_message=llm_decision,
            )

        else:
            return self.actions.create_ticket(
                title=f"Unknown anomaly: {atype}",
                description=llm_decision or anomaly.get("description", ""),
                priority="medium",
            )

    def _rule_based_decision(self, anomaly_type: str) -> str:
        rules = {
            "server_down":     "Restart the affected server immediately via SSH.",
            "high_cpu":        "Investigate top processes and consider horizontal scaling.",
            "shipping_delay":  "Send a personalised apology email to the affected customer.",
            "sla_breach":      "Notify account manager and process customer refund immediately.",
        }
        return rules.get(anomaly_type, "Create a support ticket and escalate to on-call team.")

    def run_loop(self, cycles: int = 3) -> list[dict]:
        """
        Run the full Sentinel-AI pipeline for `cycles` iterations.
        Returns list of incident summaries.
        """
        try:
            from langgraph.graph import StateGraph, END
            USE_LANGGRAPH = True
        except ImportError:
            USE_LANGGRAPH = False
            print("[Orchestrator] LangGraph not available — running sequential pipeline.")

        results = []

        for i in range(cycles):
            print(f"\n{'='*50}")
            print(f" SENTINEL-AI CYCLE {i+1}/{cycles}")
            print(f"{'='*50}")

            state: SentinelState = {
                "anomaly": None, "context": "", "llm_decision": "",
                "action_taken": "", "action_result": None,
                "escalate": False, "incident_id": "",
            }

            if USE_LANGGRAPH:
                # Build LangGraph pipeline
                graph = StateGraph(SentinelState)
                graph.add_node("monitor",          self.node_monitor)
                graph.add_node("retrieve_context", self.node_retrieve_context)
                graph.add_node("llm_reason",       self.node_llm_reason)
                graph.add_node("execute_action",   self.node_execute_action)
                graph.add_node("log_incident",     self.node_log_incident)

                graph.set_entry_point("monitor")
                graph.add_edge("monitor",          "retrieve_context")
                graph.add_edge("retrieve_context", "llm_reason")
                graph.add_edge("llm_reason",       "execute_action")
                graph.add_edge("execute_action",   "log_incident")
                graph.add_edge("log_incident",     END)

                app = graph.compile()
                state = app.invoke(state)
            else:
                # Sequential fallback
                state = self.node_monitor(state)
                state = self.node_retrieve_context(state)
                state = self.node_llm_reason(state)
                state = self.node_execute_action(state)
                state = self.node_log_incident(state)

            results.append(state)

        print(f"\n[Orchestrator] All {cycles} cycles complete.")
        return results
