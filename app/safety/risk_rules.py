from __future__ import annotations

from dataclasses import dataclass

@dataclass
class RiskDecision:
    level: str
    required_role: str | None
    auto_execute: bool
    blocked: bool
    reason: str


def assess(action_type: str, amount: float = 0.0, within_policy: bool = True, row_count: int = 1) -> RiskDecision:
    if action_type in {"bulk_delete", "delete"} or row_count > 10:
        return RiskDecision("critical", None, False, True, "Bulk changes/deletes are blocked from chat")
    if action_type == "refund":
        if not within_policy or amount > 25000:
            return RiskDecision("high", "admin", False, False, "Outside policy window or amount exceeds manager limit")
        if amount > 2000:
            return RiskDecision("medium", "manager", False, False, "Refund requires manager approval")
        return RiskDecision("low", None, True, False, "Low-risk refund within policy")
    if action_type == "change_tier":
        return RiskDecision("medium", "manager", False, False, "Changing customer tier can affect pricing")
    return RiskDecision("low", None, True, False, "Low-risk action")
