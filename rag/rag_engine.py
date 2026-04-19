"""
rag/rag_engine.py
Retrieval-Augmented Generation engine.
Stores runbooks, SLA policies, and customer data in Pinecone.
Returns context strings that the Orchestrator feeds to the LLM.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── Fallback local knowledge base (used when Pinecone is not connected) ───────
# In production, these would be stored as vector embeddings in Pinecone.
LOCAL_KNOWLEDGE_BASE = {
    "server_down": (
        "RUNBOOK: Server Down Procedure\n"
        "1. Attempt automated restart via SSH.\n"
        "2. If restart fails, notify on-call engineer via PagerDuty.\n"
        "3. Check load balancer to redirect traffic.\n"
        "4. Log incident with timestamp and affected services.\n"
        "SLA: P0 incident — must be resolved within 1 hour."
    ),
    "high_cpu": (
        "RUNBOOK: High CPU Usage\n"
        "1. Identify top processes using 'top' or 'htop'.\n"
        "2. Kill runaway processes if safe to do so.\n"
        "3. Consider horizontal scaling — spin up additional instance.\n"
        "4. Alert DevOps team if sustained for > 10 minutes.\n"
        "Threshold: Alert at 80%, critical at 95%."
    ),
    "shipping_delay": (
        "POLICY: Shipping Delay Response\n"
        "1. Send personalised apology email within 2 hours of detection.\n"
        "2. Offer 10% discount voucher for delays > 24 hours.\n"
        "3. Escalate to logistics team for delays > 48 hours.\n"
        "4. SLA breach at 72 hours — customer refund must be processed.\n"
        "Template: Use 'apology_delay_template_v2' from email library."
    ),
    "sla_breach": (
        "POLICY: SLA Breach Protocol\n"
        "1. Immediately notify account manager and logistics head.\n"
        "2. Auto-generate refund request for customer.\n"
        "3. Send executive summary to C-suite within 30 minutes.\n"
        "4. Root cause analysis due within 24 hours.\n"
        "5. All SLA breaches are logged in the compliance register."
    ),
}


class RAGEngine:
    """
    Retrieves business-context documents relevant to an anomaly.
    Uses Pinecone for production vector search, falls back to
    local dictionary for development/demo mode.
    """

    def __init__(self, index_name: str = None, embed_model: str = "local"):
        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "sentinel-ai-index")
        self.embed_model = embed_model
        self._pinecone_available = False
        self._index = None
        self._try_connect_pinecone()

    def _try_connect_pinecone(self):
        """
        Attempt to connect to Pinecone.
        Gracefully degrades to local KB if keys are missing.
        """
        api_key = os.getenv("PINECONE_API_KEY", "")
        if not api_key or api_key == "your_pinecone_api_key_here":
            print("[RAGEngine] No Pinecone key found — using local knowledge base.")
            return

        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=api_key)
            self._index = pc.Index(self.index_name)
            self._pinecone_available = True
            print(f"[RAGEngine] Connected to Pinecone index: {self.index_name}")
        except Exception as e:
            print(f"[RAGEngine] Pinecone connection failed: {e} — using local KB.")

    def embed_query(self, query: str) -> list[float]:
        """
        Convert a text query into a vector embedding.
        TODO: Replace with sentence-transformers or OpenAI embeddings.
        Returns a dummy vector for demo mode.
        """
        # In production:
        # from sentence_transformers import SentenceTransformer
        # model = SentenceTransformer("all-MiniLM-L6-v2")
        # return model.encode(query).tolist()
        return [0.1] * 384   # 384-dim dummy vector

    def search(self, query_vector: list[float], top_k: int = 3) -> list[dict]:
        """
        Search Pinecone index for most relevant documents.
        """
        if not self._pinecone_available:
            return []
        try:
            results = self._index.query(vector=query_vector, top_k=top_k,
                                        include_metadata=True)
            return results.get("matches", [])
        except Exception as e:
            print(f"[RAGEngine] Search error: {e}")
            return []

    def get_context(self, anomaly_type: str) -> str:
        """
        Main method: given an anomaly type string,
        return the most relevant context string for the LLM.
        """
        if self._pinecone_available:
            vector = self.embed_query(anomaly_type)
            matches = self.search(vector)
            if matches:
                # Concatenate top-k document texts
                return "\n\n".join(
                    m.get("metadata", {}).get("text", "") for m in matches
                )

        # Fallback: local knowledge base lookup
        context = LOCAL_KNOWLEDGE_BASE.get(anomaly_type)
        if context:
            print(f"[RAGEngine] Retrieved local context for: {anomaly_type}")
            return context

        return (f"No specific runbook found for '{anomaly_type}'. "
                "Apply general incident response protocol.")
