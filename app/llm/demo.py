from __future__ import annotations

import re

from dataclasses import dataclass

@dataclass
class DemoResult:
    text: str
    data: dict

class DemoLLM:
    """Deterministic offline model used only for the documented demo scenarios."""

    def classify(self, text: str) -> str:
        t = text.lower()
        if any(x in t for x in ["delete", "drop", "truncate", "erase", "remove all", "reveal the system prompt", "forget all instructions"]):
            return "refuse_or_clarify"
        if any(x in t for x in ["refund", "escalate", "draft email", "change tier"]):
            return "action"
        if any(x in t for x in ["policy", "return window", "refund window", "discount", "shipping", "privacy"]):
            return "policy"
        if "ticket" in t and ("summarise" in t or "summarize" in t):
            return "analytics"
        if any(x in t for x in ["remember", "what did i tell you to remember"]):
            return "memory"
        return "analytics"

    def sql(self, text: str) -> str:
        t = text.lower()

        # Read-only refund status lookup. This is deliberately separate from
        # the action path so asking for status never creates a new refund.
        status_match = re.search(r"order\s*#?\s*(\d+)", text, re.I)
        if status_match and "refund" in t and any(
            phrase in t for phrase in (
                "refund status",
                "status of refund",
                "refund record",
                "current status",
                "was the refund",
                "refund processed",
                "refund completed",
                "refund approved",
            )
        ):
            order_id = int(status_match.group(1))
            return (
                "SELECT o.id AS order_id, o.status AS order_status, "
                "r.id AS refund_id, r.amount, r.reason, r.status AS refund_status, "
                "r.approved_by, r.created_at "
                "FROM orders o LEFT JOIN refunds r ON r.order_id = o.id "
                f"WHERE o.id = {order_id} LIMIT 1"
            )

        if "ticket" in t and ("summarise" in t or "summarize" in t):
            return "SELECT id, order_id, subject, body, priority, status FROM tickets WHERE id = 57 LIMIT 1"
        if "top 5" in t and "revenue" in t:
            return "SELECT p.name, ROUND(SUM(oi.quantity * oi.price), 2) AS revenue FROM order_items oi JOIN products p ON p.id = oi.product_id JOIN orders o ON o.id = oi.order_id WHERE o.order_date >= date('now','-3 months') GROUP BY p.id ORDER BY revenue DESC LIMIT 5"
        if "hyderabad" in t and "3 orders" in t:
            return "SELECT c.id, c.name, COUNT(o.id) AS order_count FROM customers c JOIN orders o ON o.customer_id = c.id WHERE lower(c.city) = 'hyderabad' GROUP BY c.id HAVING COUNT(o.id) > 3 ORDER BY order_count DESC LIMIT 500"
        if "revenue" in t:
            return "SELECT ROUND(SUM(total),2) AS revenue FROM orders WHERE order_date >= date('now','-3 months') LIMIT 1"
        return "SELECT id, name, city, tier FROM customers LIMIT 10"

    def response(self, text: str, context: str) -> str:
        t = text.lower()
        if "remember" in t and "what did i tell" not in t:
            return "I will store that preference in your JNMV AuditPilot memory."
        if "what did i tell you to remember" in t:
            return context or "I do not have a saved preference for this user yet."
        if "return window" in t or "electronics" in t or "travel essentials" in t:
            return "For JNMV Overseas, travel essentials can be returned within 10 days of delivery; damaged goods are eligible within that window. Source: refund_policy.md, Refund window."
        if "delete all" in t:
            return "I cannot perform bulk deletion from chat. The request is blocked and logged as unsafe."
        return context or "Demo Mode is active. Try one of the README demo prompts."
