from __future__ import annotations

from typing import Any, TypedDict

class AgentState(TypedDict, total=False):
    session_id: str
    user_id: int
    user_email: str
    role: str
    messages: list[dict[str, str]]
    user_message: str
    intent: str
    plan: str
    sql: str
    rows: list[dict[str, Any]]
    policy_chunks: list[dict[str, str]]
    proposed_action: dict[str, Any]
    risk: dict[str, Any]
    approval_status: str
    final_answer: str
    confidence: str
    critic_verdict: str
    guard_events: list[str]
    evidence: dict[str, Any]
