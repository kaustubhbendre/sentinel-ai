"""
actions/action_engine.py
Executes autonomous actions decided by the Orchestrator.
Supports: server restart, apology email, ticket creation.
"""

import os
import smtplib
import json
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ActionResult:
    """Result of an executed action."""
    action_type: str
    success: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class ActionEngine:
    """
    Executes pre-approved autonomous remediation actions.
    Each method returns an ActionResult so the Orchestrator
    knows whether to escalate or close the incident.
    """

    def __init__(self, action_type: str = "generic", confidence: float = 0.9):
        self.action_type = action_type
        self.confidence = confidence
        self._email_sender = os.getenv("EMAIL_SENDER", "")
        self._email_password = os.getenv("EMAIL_PASSWORD", "")

    # ── 1. Restart Server ──────────────────────────────────────────────────
    def restart_server(self, server_name: str) -> ActionResult:
        """
        Attempts to restart a named server via SSH command.
        TODO: Replace simulation with real paramiko SSH call.
        
        Real implementation:
            import paramiko
            client = paramiko.SSHClient()
            client.connect(server_ip, username="admin", key_filename="~/.ssh/id_rsa")
            stdin, stdout, stderr = client.exec_command("sudo systemctl restart myapp")
        """
        print(f"[ActionEngine] Attempting restart on: {server_name}")

        # Simulate success (80% of the time in demo)
        import random
        success = random.random() > 0.2

        if success:
            return ActionResult(
                action_type="restart_server",
                success=True,
                message=f"Server '{server_name}' restarted successfully.",
                details={"server": server_name, "method": "ssh_restart"},
            )
        else:
            return ActionResult(
                action_type="restart_server",
                success=False,
                message=f"Restart failed for '{server_name}'. Escalating to on-call engineer.",
                details={"server": server_name, "error": "SSH timeout"},
            )

    # ── 2. Send Apology Email ──────────────────────────────────────────────
    def send_email(self, recipient: str, customer_name: str,
                   order_id: str, delay_hours: float,
                   llm_message: str = "") -> ActionResult:
        """
        Sends a personalised apology email to the customer.
        Uses Gmail SMTP. Add EMAIL_SENDER and EMAIL_PASSWORD to .env.
        """
        subject = f"Important Update About Your Order {order_id}"

        # Use LLM-generated message if provided, else use default template
        body = llm_message or self._default_apology_template(
            customer_name, order_id, delay_hours
        )

        if (not self._email_sender
                or self._email_sender == "youremail@gmail.com"
                or not self._email_password
                or self._email_password == "your_app_password_here"):
            # Demo mode — print instead of sending
            print(f"\n[ActionEngine] EMAIL (demo mode — not actually sent)")
            print(f"  To: {recipient}")
            print(f"  Subject: {subject}")
            print(f"  Body:\n{body}\n")
            return ActionResult(
                action_type="send_email",
                success=True,
                message=f"Apology email drafted for {customer_name} (demo mode).",
                details={"recipient": recipient, "order_id": order_id},
            )

        # Real SMTP send
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._email_sender
            msg["To"] = recipient
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_sender, self._email_password)
                server.sendmail(self._email_sender, recipient, msg.as_string())

            return ActionResult(
                action_type="send_email",
                success=True,
                message=f"Apology email sent to {recipient}.",
                details={"recipient": recipient, "order_id": order_id},
            )
        except Exception as e:
            return ActionResult(
                action_type="send_email",
                success=False,
                message=f"Email failed: {e}",
                details={"error": str(e)},
            )

    # ── 3. Create Support Ticket ───────────────────────────────────────────
    def create_ticket(self, title: str, description: str,
                      priority: str = "high") -> ActionResult:
        """
        Creates an incident ticket in your ticketing system.
        TODO: Replace with real Jira/ServiceNow API call.
        """
        ticket_id = f"TKT-{int(datetime.now().timestamp())}"
        print(f"[ActionEngine] Ticket created: {ticket_id} | {title}")
        return ActionResult(
            action_type="create_ticket",
            success=True,
            message=f"Ticket {ticket_id} created successfully.",
            details={"ticket_id": ticket_id, "title": title, "priority": priority},
        )

    def log_result(self, result: ActionResult) -> None:
        """Write action result to a local log file."""
        log_path = "data/action_log.jsonl"
        os.makedirs("data", exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")
        print(f"[ActionEngine] Logged result → {log_path}")

    # ── Private helpers ────────────────────────────────────────────────────
    def _default_apology_template(self, name: str, order_id: str,
                                  delay_hours: float) -> str:
        delay_days = int(delay_hours // 24)
        delay_str = f"{delay_days} day(s)" if delay_days >= 1 else f"{int(delay_hours)} hour(s)"
        return (
            f"Dear {name},\n\n"
            f"We sincerely apologise for the delay in delivering your order {order_id}. "
            f"Your order is currently {delay_str} behind schedule due to unexpected "
            f"logistics disruptions.\n\n"
            f"We are working urgently to resolve this and will provide an updated "
            f"delivery estimate within 24 hours. As a token of our apology, a 10% "
            f"discount has been applied to your next order.\n\n"
            f"Thank you for your patience.\n\nWarm regards,\nSentinel-AI Support Team"
        )