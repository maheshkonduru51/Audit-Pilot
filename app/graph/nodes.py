from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.audit.audit_log import append_event
from app.config import settings
from app.db.models import PendingAction
from app.db.session import SessionLocal
from app.graph.state import AgentState
from app.llm.client import llm_client
from app.memory.long_term import get_preferences, store_preference
from app.safety.injection_filter import scan_untrusted
from app.safety.risk_rules import assess
from app.tools.action_tools import execute_action, find_order, find_ticket
from app.tools.policy_tool import policy_search
from app.tools.sql_tool import run_safe_sql, schema_text


def audit(state: AgentState, event: str, payload: dict[str, Any] | None = None) -> None:
    append_event(state["user_email"], state["session_id"], event, payload or {})


def classify_intent(state: AgentState) -> AgentState:
    text = state["user_message"]

    # A refund-status question is read-only. Route it to analytics before
    # consulting the LLM so neither Real nor Demo mode can accidentally turn
    # a status lookup into a new refund action.
    status_query = re.search(
        r"(?:\b(refund\s+(?:status|record|details|information)|"
        r"status\s+of\s+refund|current\s+(?:refund|refund\s+status)|"
        r"was\s+the\s+refund|show\s+(?:me\s+)?(?:the\s+)?refund|"
        r"refund.*\b(?:processed|completed|approved|status|details|information)\b)\b)",
        text,
        re.I,
    )

    if status_query:
        intent = "analytics"
    elif settings.llm_mode == "real":
        result = llm_client.json(
            'Classify the request. Return exactly {"intent":"analytics|policy|action|refuse_or_clarify|memory"}.',
            text,
        )
        intent = result.get("intent", "analytics")
    else:
        intent = llm_client.demo.classify(text)
    if intent not in {"analytics", "policy", "action", "refuse_or_clarify", "memory"}:
        intent = "refuse_or_clarify"
    state["intent"] = intent
    state["guard_events"] = scan_untrusted(text)
    audit(state, "classify_intent", {"intent": intent, "guard_events": state["guard_events"]})
    return state


def plan(state: AgentState) -> AgentState:
    text = state["user_message"]
    if state["intent"] == "analytics":
        if settings.llm_mode == "real":
            result = llm_client.json(
                'You are a safe analytics planner. Return JSON {"sql": string, "reason": string}. SQL must be one read-only SELECT/WITH query and must use only the provided SQLite tables.',
                f"Schema:\n{schema_text()}\n\nQuestion:\n{text}",
            )
            state["sql"] = result.get("sql", "")
            state["plan"] = result.get("reason", "Generate a read-only SQL query.")
        else:
            state["sql"] = llm_client.demo.sql(text)
            state["plan"] = "Translate the business question into a read-only SQL query and validate it."
    elif state["intent"] == "action":
        state["plan"] = "Gather order/ticket facts, retrieve policy evidence, assess risk, then execute or request approval."
    audit(state, "plan", {"plan": state.get("plan", "")})
    return state


def sql_tool(state: AgentState) -> AgentState:
    try:
        rows, sql, validation = run_safe_sql(state.get("sql", ""), state["role"])
        state["sql"] = sql
        state["rows"] = rows
        state["evidence"] = {"sql_validation": validation}
        # Scan tool output too: a malicious ticket body is data, not instructions.
        tool_text = json.dumps(rows, default=str)
        state["guard_events"] = list(dict.fromkeys(state.get("guard_events", []) + scan_untrusted(tool_text)))
        state["confidence"] = "High" if rows else "Medium"
        audit(state, "sql_tool", {"sql": sql, "row_count": len(rows), "guard_events": state["guard_events"]})
    except Exception as exc:
        state["final_answer"] = f"I could not safely execute the SQL: {exc}"
        state["confidence"] = "Low"
        audit(state, "sql_tool_error", {"error": str(exc)})
    return state


def policy_node(state: AgentState) -> AgentState:
    chunks = policy_search.search(state["user_message"], 3)
    state["policy_chunks"] = chunks
    evidence = "\n\n".join([f"{c['doc']} - {c['section']}: {c['text']}" for c in chunks])
    if settings.llm_mode == "real":
        state["final_answer"] = llm_client.text(
            "Answer only from the supplied policy excerpts. Cite claims in the format [document, section]. If unsupported, say so.",
            f"Question: {state['user_message']}\n\nPolicy excerpts:\n{evidence}",
        )
    else:
        state["final_answer"] = llm_client.demo.response(state["user_message"], evidence)
    state["confidence"] = "High" if chunks else "Low"
    audit(state, "policy_search", {"chunks": chunks})
    return state


def gather_facts(state: AgentState) -> AgentState:
    text = state["user_message"]
    order_match = re.search(r"order\s*#?\s*(\d+)", text, re.I)
    ticket_match = re.search(r"ticket\s*#?\s*(\d+)", text, re.I)
    facts: dict[str, Any] = {}
    if order_match:
        facts["order"] = find_order(int(order_match.group(1)))
    if ticket_match:
        facts["ticket"] = find_ticket(int(ticket_match.group(1)))
    state["evidence"] = {**state.get("evidence", {}), **facts}
    guard_events = list(state.get("guard_events", []))
    if facts.get("ticket"):
        guard_events.extend(scan_untrusted(facts["ticket"].get("body", "")))
    state["guard_events"] = list(dict.fromkeys(guard_events))
    audit(state, "gather_facts", {"facts": facts, "guard_events": state["guard_events"]})
    return state


def propose_action(state: AgentState) -> AgentState:
    text = state["user_message"]
    t = text.lower()
    if "refund" in t:
        order = state.get("evidence", {}).get("order")
        if not order:
            state["proposed_action"] = {"action_type": "refund", "amount": 0, "reason": "Order not found"}
        else:
            requested = order["total"]
            if "half" in t:
                requested = round(order["total"] / 2, 2)
            state["proposed_action"] = {"action_type": "refund", "order_id": order["order_id"], "amount": requested, "reason": text}
    elif "escalate" in t and state.get("evidence", {}).get("ticket"):
        state["proposed_action"] = {"action_type": "escalate_ticket", "ticket_id": state["evidence"]["ticket"]["id"], "reason": text}
    elif "draft" in t and "email" in t:
        state["proposed_action"] = {"action_type": "draft_email", "subject": "JNMV follow-up", "body": text}
    else:
        state["proposed_action"] = {"action_type": "unknown", "reason": text}
    audit(state, "propose_action", state["proposed_action"])
    return state


def risk_check(state: AgentState) -> AgentState:
    action = state.get("proposed_action", {})
    amount = float(action.get("amount", 0.0))
    within_policy = True
    if action.get("action_type") == "refund":
        order = state.get("evidence", {}).get("order") or {}
        delivered_at = order.get("delivered_at")
        if delivered_at:
            days = (datetime.utcnow() - datetime.fromisoformat(delivered_at)).days
            within_policy = days <= 10
        else:
            within_policy = False
    decision = assess(action.get("action_type", "unknown"), amount=amount, within_policy=within_policy)
    state["risk"] = decision.__dict__
    audit(state, "risk_check", state["risk"])
    if decision.blocked:
        state["final_answer"] = f"Blocked: {decision.reason}."
    return state


def wait_for_approval(state: AgentState) -> AgentState:
    action = dict(state["proposed_action"])
    action["_requested_by"] = state["user_email"]
    db = SessionLocal()
    try:
        db.add(PendingAction(session_id=state["session_id"], action_type=action.get("action_type", "unknown"), payload_json=json.dumps(action), risk_level=state["risk"]["level"], required_role=state["risk"]["required_role"], status="pending", evidence_json=json.dumps(state.get("evidence", {}), default=str)))
        db.commit()
    finally:
        db.close()
    state["proposed_action"] = action
    state["approval_status"] = "pending"
    state["final_answer"] = f"This action requires {state['risk']['required_role']} approval before it can run. Open Approvals to review the evidence."
    audit(state, "approval_requested", {"action": action, "risk": state["risk"]})
    return state


def resume_approved_action(state: AgentState) -> AgentState:
    """Resume an already-approved action without reclassifying the request.

    This is the control-plane continuation used by the approval endpoint.
    The action has already passed intent classification, fact gathering,
    proposal, and risk checks; once a human approves it, only execution,
    verification, critique, and response should run.
    """
    state = execute(state)
    state = verify(state)
    state = critic(state)
    state = respond(state)
    return state


def execute(state: AgentState) -> AgentState:
    if state.get("guard_events") and state.get("proposed_action", {}).get("action_type") not in {"refund", "draft_email"}:
        state["final_answer"] = "The action includes untrusted instruction-like text. I treated it as data and did not obey it."
        state["confidence"] = "High"
        audit(state, "execution_blocked_guard", {"guard_events": state["guard_events"]})
        return state
    result = execute_action(state["proposed_action"], state["user_email"], state["session_id"])
    state["final_answer"] = result["message"]
    state["evidence"] = {**state.get("evidence", {}), "execution_result": result}
    state["confidence"] = "High" if result.get("ok") else "Low"
    return state


def verify(state: AgentState) -> AgentState:
    action = state.get("proposed_action", {})
    if action.get("action_type") == "refund":
        order = find_order(int(action["order_id"]))
        verified = bool(order and order["status"] == "refunded")
    elif action.get("action_type") == "escalate_ticket":
        ticket = find_ticket(int(action["ticket_id"]))
        verified = bool(ticket and ticket["status"] == "escalated")
    else:
        verified = True
    state["evidence"] = {**state.get("evidence", {}), "verified": verified}
    if verified:
        state["final_answer"] = state.get("final_answer", "") + " Verification: database state confirms the action."
    else:
        state["final_answer"] = state.get("final_answer", "") + " Verification failed; the database state was not confirmed."
        state["confidence"] = "Low"
    audit(state, "verify", {"verified": verified})
    return state


def critic(state: AgentState) -> AgentState:
    intent = state.get("intent")
    if state.get("guard_events"):
        verdict = "Guard event detected; untrusted text was not treated as instructions."
        confidence = "High"
    elif intent == "analytics":
        verdict = "Answer grounded in validated SQL result."
        confidence = state.get("confidence", "Medium")
    elif intent == "policy":
        verdict = "Answer grounded in retrieved policy excerpts."
        confidence = state.get("confidence", "High")
    elif intent == "action":
        verdict = "Action path checked against risk rules and verification state."
        confidence = state.get("confidence", "Medium")
    else:
        verdict = "Request handled conservatively."
        confidence = state.get("confidence", "High")
    state["critic_verdict"] = verdict
    state["confidence"] = confidence
    audit(state, "critic", {"verdict": verdict, "confidence": confidence})
    return state


def refuse_or_clarify(state: AgentState) -> AgentState:
    state["final_answer"] = "I cannot perform destructive or ambiguous requests from chat. The request is blocked and logged."
    state["confidence"] = "High"
    audit(state, "refuse_or_clarify", {"message": state["user_message"]})
    return state


def memory_node(state: AgentState) -> AgentState:
    text = state["user_message"].strip()
    if text.lower().startswith("remember "):
        pref = text[9:].strip()
        store_preference(state["user_id"], pref)
        state["final_answer"] = f"Saved preference: {pref}"
    else:
        prefs = get_preferences(state["user_id"])
        state["final_answer"] = "Saved preferences:\n" + "\n".join(f"- {p}" for p in prefs) if prefs else "No saved preferences yet."
    state["confidence"] = "High"
    audit(state, "memory", {"intent": "memory"})
    return state


def respond(state: AgentState) -> AgentState:
    if not state.get("final_answer") and state["intent"] == "analytics":
        rows = state.get("rows", [])
        if settings.llm_mode == "real":
            state["final_answer"] = llm_client.text(
                "Answer the analytics question using only the provided SQL result. Keep it concise and do not invent facts.",
                f"Question: {state['user_message']}\nValidated SQL: {state.get('sql','')}\nRows: {json.dumps(rows, default=str)}",
            )
        else:
            if state.get("guard_events"):
                state["final_answer"] = "Ticket summary: the ticket was retrieved, but its embedded instruction-like text was treated as untrusted data and ignored.\n\n" + json.dumps(rows, indent=2, default=str)
            else:
                state["final_answer"] = f"I ran a validated read-only SQL query and found {len(rows)} row(s).\n\n{json.dumps(rows, indent=2, default=str)}"
        state["confidence"] = state.get("confidence", "Medium")
    state.setdefault("final_answer", "No answer generated.")
    audit(state, "respond", {"confidence": state.get("confidence"), "critic_verdict": state.get("critic_verdict", "")})
    return state
