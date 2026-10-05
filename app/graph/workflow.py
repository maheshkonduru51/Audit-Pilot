from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.state import AgentState
from app.graph.nodes import (
    classify_intent, critic, execute, gather_facts, memory_node, plan, policy_node,
    propose_action, refuse_or_clarify, respond, risk_check, sql_tool, verify,
    wait_for_approval,
)


def route_after_classify(state: AgentState) -> str:
    return state.get("intent", "analytics")


def route_after_plan(state: AgentState) -> str:
    return "action" if state.get("intent") == "action" else "analytics"


def route_after_action_risk(state: AgentState) -> str:
    risk = state.get("risk", {})
    if risk.get("blocked"):
        return "critic"
    if state.get("approval_status") == "approved":
        return "execute"
    if risk.get("auto_execute"):
        return "execute"
    return "approval"


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("classify_intent", classify_intent), ("plan", plan), ("sql_tool", sql_tool),
        ("policy_search", policy_node), ("gather_facts", gather_facts), ("propose_action", propose_action),
        ("risk_check", risk_check), ("wait_for_approval", wait_for_approval), ("execute", execute),
        ("verify", verify), ("critic", critic), ("memory", memory_node),
        ("refuse_or_clarify", refuse_or_clarify), ("respond", respond)
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "classify_intent")
    g.add_conditional_edges("classify_intent", route_after_classify, {
        "analytics": "plan", "policy": "policy_search", "action": "plan",
        "refuse_or_clarify": "refuse_or_clarify", "memory": "memory",
    })
    g.add_conditional_edges("plan", route_after_plan, {"analytics": "sql_tool", "action": "gather_facts"})
    g.add_edge("sql_tool", "critic")
    g.add_edge("policy_search", "critic")
    g.add_edge("gather_facts", "propose_action")
    g.add_edge("propose_action", "risk_check")
    g.add_conditional_edges("risk_check", route_after_action_risk, {"execute": "execute", "approval": "wait_for_approval", "critic": "critic"})
    g.add_edge("execute", "verify")
    g.add_edge("verify", "critic")
    g.add_edge("critic", "respond")
    g.add_edge("respond", END)
    g.add_edge("memory", END)
    g.add_edge("refuse_or_clarify", END)
    return g.compile()

graph = build_graph()
