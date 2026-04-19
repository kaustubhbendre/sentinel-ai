"""
dashboard/app.py
Sentinel-AI live dashboard built with Streamlit.
Run with: streamlit run dashboard/app.py
"""

import json
import os
import time
import pandas as pd
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sentinel-AI Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

INCIDENT_LOG_PATH = "data/incidents.jsonl"
SEVERITY_COLOUR = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}
STATUS_COLOUR = {
    "open":        "🔴 Open",
    "in_progress": "🔵 In Progress",
    "resolved":    "🟢 Resolved",
    "escalated":   "🟠 Escalated",
}


def load_incidents() -> list[dict]:
    """Load all incidents from the JSONL log file."""
    if not os.path.exists(INCIDENT_LOG_PATH):
        return []
    incidents = []
    with open(INCIDENT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    incidents.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return incidents


def run_sentinel(cycles: int = 1):
    """Trigger the orchestrator pipeline from the dashboard."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from orchestrator import Orchestrator
    orch = Orchestrator()
    with st.spinner("🤖 Sentinel-AI agents running..."):
        orch.run_loop(cycles=cycles)
    st.success(f"✅ {cycles} monitoring cycle(s) complete!")
    time.sleep(1)
    st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=64)
    st.title("Sentinel-AI")
    st.caption("Preemptive Multi-Agent Support Engine")
    st.divider()

    st.subheader("⚙️ Controls")
    cycles = st.slider("Monitoring cycles", 1, 10, 3)
    if st.button("▶ Run Sentinel-AI", type="primary", use_container_width=True):
        run_sentinel(cycles)

    if st.button("🗑 Clear Incident Log", use_container_width=True):
        if os.path.exists(INCIDENT_LOG_PATH):
            os.remove(INCIDENT_LOG_PATH)
        st.rerun()

    st.divider()
    st.caption("Auto-refresh every 10 seconds")
    auto = st.toggle("Auto-refresh", value=False)

# ── Main Content ──────────────────────────────────────────────────────────────
st.title("🛡️ Sentinel-AI — Live Operations Dashboard")
st.caption("Real-time IT and Business monitoring powered by Agentic AI")
st.divider()

incidents = load_incidents()

# ── KPI Cards ─────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
total      = len(incidents)
resolved   = sum(1 for i in incidents if i["status"] == "resolved")
escalated  = sum(1 for i in incidents if i["status"] == "escalated")
open_inc   = sum(1 for i in incidents if i["status"] == "open")

col1.metric("Total Incidents",   total)
col2.metric("✅ Resolved",       resolved)
col3.metric("🟠 Escalated",      escalated)
col4.metric("🔴 Open",           open_inc)
st.divider()

# ── Incident Table ────────────────────────────────────────────────────────────
st.subheader("📋 Incident Log")

if not incidents:
    st.info("No incidents yet. Click **▶ Run Sentinel-AI** in the sidebar to start monitoring.")
else:
    # Build dataframe
    rows = []
    for inc in reversed(incidents):  # newest first
        rows.append({
            "ID":          inc["incident_id"],
            "Severity":    SEVERITY_COLOUR.get(inc["severity"], "⚪") + " " + inc["severity"].upper(),
            "Type":        inc["anomaly_type"].replace("_", " ").title(),
            "Description": inc["description"][:80] + "..." if len(inc["description"]) > 80 else inc["description"],
            "Status":      STATUS_COLOUR.get(inc["status"], inc["status"]),
            "Agent":       inc["agent_id"],
            "Time":        inc["created_at"][:19].replace("T", " "),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Incident Detail Expanders ─────────────────────────────────────────
    st.subheader("🔍 Incident Details")
    for inc in reversed(incidents[-5:]):   # Show last 5
        sev_icon = SEVERITY_COLOUR.get(inc["severity"], "⚪")
        with st.expander(f"{sev_icon} {inc['incident_id']} — {inc['anomaly_type'].replace('_', ' ').title()}"):
            c1, c2 = st.columns(2)
            c1.write(f"**Description:** {inc['description']}")
            c1.write(f"**Severity:** {inc['severity'].upper()}")
            c1.write(f"**Status:** {inc['status'].upper()}")
            c2.write(f"**Agent:** {inc['agent_id']}")
            c2.write(f"**Created:** {inc['created_at'][:19]}")
            if inc.get("resolved_at"):
                c2.write(f"**Resolved:** {inc['resolved_at'][:19]}")

            if inc.get("llm_reasoning"):
                st.info(f"🤖 **LLM Reasoning:** {inc['llm_reasoning']}")

            if inc.get("actions_taken"):
                st.write("**Actions taken:**")
                for act in inc["actions_taken"]:
                    st.write(f"  • {act['action']} at {act['timestamp'][:19]}")

            if inc.get("metadata"):
                st.json(inc["metadata"])

# ── Severity Bar Chart ────────────────────────────────────────────────────────
if incidents:
    st.divider()
    st.subheader("📊 Incidents by Severity")
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for inc in incidents:
        sev = inc.get("severity", "low")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
    sev_df = pd.DataFrame(
        list(sev_counts.items()), columns=["Severity", "Count"]
    )
    st.bar_chart(sev_df.set_index("Severity"))

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto:
    time.sleep(10)
    st.rerun()
