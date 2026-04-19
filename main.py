"""
main.py
Entry point for Sentinel-AI.
Run this to start the monitoring pipeline from the terminal.
"""

import sys
import os

# Add project root so all modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import Orchestrator


def main():
    print("=" * 60)
    print("  SENTINEL-AI — Preemptive Multi-Agent Support Engine")
    print("  BSc IT Final Year Project")
    print("=" * 60)

    orch = Orchestrator()
    results = orch.run_loop(cycles=3)

    print("\n" + "=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)
    for i, state in enumerate(results, 1):
        anomaly = state.get("anomaly")
        if anomaly:
            print(f"  Cycle {i}: [{anomaly['severity'].upper()}] "
                  f"{anomaly['anomaly_type']} → "
                  f"{'ESCALATED' if state.get('escalate') else 'RESOLVED'} "
                  f"| Incident: {state.get('incident_id', 'N/A')}")
        else:
            print(f"  Cycle {i}: No anomalies detected.")

    print("\n✅ Done. Check data/incidents.jsonl for the full log.")
    print("   Run the dashboard with: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
