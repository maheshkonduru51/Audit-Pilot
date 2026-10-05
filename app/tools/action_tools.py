from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.audit.audit_log import append_event
from app.db.models import Customer, Order, Outbox, Refund, Ticket
from app.db.session import SessionLocal
from app.safety.risk_rules import assess


def find_order(order_id: int) -> dict | None:
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            return None
        customer = db.get(Customer, order.customer_id)
        return {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "customer_name": customer.name if customer else "Unknown",
            "customer_tier": customer.tier if customer else "unknown",
            "total": float(order.total),
            "status": order.status,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        }
    finally:
        db.close()


def find_ticket(ticket_id: int) -> dict | None:
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            return None
        return {"id": ticket.id, "order_id": ticket.order_id, "subject": ticket.subject, "body": ticket.body, "priority": ticket.priority, "status": ticket.status}
    finally:
        db.close()


def execute_action(action: dict, actor: str, session_id: str) -> dict:
    action_type = action["action_type"]
    db = SessionLocal()
    try:
        if action_type == "refund":
            order_id = int(action["order_id"])
            amount = float(action["amount"])
            row = db.get(Order, order_id)
            if not row:
                return {"ok": False, "message": "Order not found"}
            db.add(Refund(order_id=order_id, amount=amount, reason=action.get("reason", "Agent refund"), status="processed", approved_by=actor, created_at=datetime.utcnow()))
            row.status = "refunded"
            db.commit()
            result = {"ok": True, "message": f"Refund of Rs {amount:,.2f} recorded for order {order_id}.", "order_id": order_id}
        elif action_type == "escalate_ticket":
            ticket_id = int(action["ticket_id"])
            row = db.get(Ticket, ticket_id)
            if not row:
                return {"ok": False, "message": "Ticket not found"}
            row.priority = "high"
            row.status = "escalated"
            db.commit()
            result = {"ok": True, "message": f"Ticket {ticket_id} escalated."}
        elif action_type == "draft_email":
            db.add(Outbox(to_email=action.get("to_email", "support@jnmv.com"), subject=action.get("subject", "JNMV follow-up"), body=action.get("body", ""), status="draft", created_at=datetime.utcnow()))
            db.commit()
            result = {"ok": True, "message": "Customer email saved as a draft; it was not sent."}
        elif action_type == "change_tier":
            customer_id = int(action["customer_id"])
            row = db.get(Customer, customer_id)
            if not row:
                return {"ok": False, "message": "Customer not found"}
            row.tier = action["new_tier"]
            db.commit()
            result = {"ok": True, "message": f"Customer {customer_id} changed to tier {action['new_tier']}."}
        else:
            result = {"ok": False, "message": f"Unsupported action: {action_type}"}
        append_event(actor, session_id, "action_executed", result | {"action": action})
        return result
    finally:
        db.close()
