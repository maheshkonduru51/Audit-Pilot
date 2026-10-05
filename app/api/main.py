from __future__ import annotations

import json
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import select

from app.audit.audit_log import append_event, verify_chain
from app.config import settings
from app.db.models import AuditLog, EvalResult, Memory, PendingAction, User
from app.db.session import SessionLocal, init_db
from app.graph.workflow import graph
from app.graph.nodes import resume_approved_action
from app.memory.session_memory import add_message, get_messages
from app.api.auth import create_token, decode_token
from app.api.schemas import ApprovalDecision, ChatRequest, LoginRequest

app = FastAPI(title="AuditPilot - JNMV Overseas Pvt. Ltd.", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
init_db()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return decode_token(authorization.split(" ", 1)[1])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


def role_required(user: dict, roles: set[str]) -> None:
    if user.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Insufficient role")

@app.get("/health")
def health():
    return {"status": "ok", "company": settings.company_name, "default_mode": settings.llm_mode, "model": settings.llm_model}

@app.post("/auth/login")
def login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == req.email)).scalars().first()
        if not user or not pwd_context.verify(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"access_token": create_token(user.id, user.email, user.role), "user": {"id": user.id, "email": user.email, "role": user.role, "name": user.name}}
    finally:
        db.close()

@app.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(current_user)):
    original_mode = settings.llm_mode
    object.__setattr__(settings, "llm_mode", req.mode)
    session_id = req.session_id or str(uuid.uuid4())
    state = {
        "session_id": session_id,
        "user_id": int(user["sub"]),
        "user_email": user["email"],
        "role": user["role"],
        "messages": get_messages(session_id),
        "user_message": req.message,
        "approval_status": "",
    }
    add_message(session_id, "user", req.message)
    try:
        result = graph.invoke(state)
    except Exception as exc:
        result = {**state, "final_answer": f"Agent error: {exc}", "confidence": "Low"}
    finally:
        object.__setattr__(settings, "llm_mode", original_mode)
    add_message(session_id, "assistant", result.get("final_answer", ""))
    return {
        "session_id": session_id, "mode": req.mode, "answer": result.get("final_answer", ""),
        "intent": result.get("intent"), "plan": result.get("plan"), "sql": result.get("sql"),
        "rows": result.get("rows", []), "policy_chunks": result.get("policy_chunks", []),
        "confidence": result.get("confidence", "Medium"), "critic_verdict": result.get("critic_verdict"),
        "risk": result.get("risk"), "guard_events": result.get("guard_events", []), "evidence": result.get("evidence", {}),
    }


@app.get("/sessions/{session_id}")
def session(session_id: str, user: dict = Depends(current_user)):
    return {"session_id": session_id, "messages": get_messages(session_id)}

@app.get("/data/schema")
def data_schema(user: dict = Depends(current_user)):
    role_required(user, {"analyst", "manager", "admin"})
    from app.tools.sql_tool import schema_text
    return {"schema": schema_text()}

@app.post("/eval/run")
def eval_run(user: dict = Depends(current_user)):
    role_required(user, {"admin"})
    from eval_agent import run
    run()
    return {"ok": True, "message": "Evaluation completed. See /eval/results."}

@app.get("/approvals")
def approvals(user: dict = Depends(current_user)):
    role_required(user, {"manager", "admin"})
    db = SessionLocal()
    try:
        rows = db.execute(select(PendingAction).where(PendingAction.status == "pending").order_by(PendingAction.id.desc())).scalars().all()
        return [{"id": r.id, "action_type": r.action_type, "risk_level": r.risk_level, "required_role": r.required_role, "session_id": r.session_id, "payload": json.loads(r.payload_json), "evidence": json.loads(r.evidence_json)} for r in rows]
    finally:
        db.close()

@app.post("/approvals/{action_id}/approve")
def approve(action_id: int, req: ApprovalDecision, user: dict = Depends(current_user)):
    """Approve a pending action and resume it directly at execute -> verify."""
    role_required(user, {"manager", "admin"})

    db = SessionLocal()
    try:
        row = db.get(PendingAction, action_id)
        if not row or row.status != "pending":
            raise HTTPException(status_code=404, detail="Pending action not found")
        if row.required_role == "admin" and user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin approval required")

        action = json.loads(row.payload_json)
        if action.get("_requested_by") == user["email"]:
            raise HTTPException(status_code=403, detail="A user cannot approve their own request")

        session_id = row.session_id
        evidence = json.loads(row.evidence_json)
        required_role = row.required_role
        risk_level = row.risk_level
        requester_email = action.get("_requested_by", "")

        row.status = "approved"
        row.decided_by = user["email"]
        row.decided_at = __import__("datetime").datetime.utcnow()
        db.commit()
    finally:
        db.close()

    append_event(
        user["email"],
        session_id,
        "approval_decision",
        {
            "action_id": action_id,
            "decision": "approved",
            "comment": req.comment,
            "required_role": required_role,
            "action": action,
        },
    )

    state = {
        "session_id": session_id,
        "user_id": int(user["sub"]),
        "user_email": user["email"],
        "role": user["role"],
        "user_message": f"Approved action #{action_id}",
        "intent": "action",
        "proposed_action": action,
        "risk": {"level": risk_level, "required_role": required_role},
        "approval_status": "approved",
        "evidence": evidence,
        "guard_events": [],
    }

    try:
        result = resume_approved_action(state)
    except Exception as exc:
        append_event(
            user["email"],
            session_id,
            "execution_error",
            {"action_id": action_id, "error": str(exc)},
        )
        db = SessionLocal()
        try:
            row = db.get(PendingAction, action_id)
            if row:
                row.status = "execution_failed"
                row.evidence_json = json.dumps({**evidence, "execution_error": str(exc)}, default=str)
                db.commit()
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"Approved action failed during execution: {exc}") from exc

    verified = bool(result.get("evidence", {}).get("verified"))
    execution_ok = bool(result.get("evidence", {}).get("execution_result", {}).get("ok"))
    final_status = "executed" if (verified and execution_ok) else "execution_failed"

    db = SessionLocal()
    try:
        row = db.get(PendingAction, action_id)
        if row:
            row.status = final_status
            row.evidence_json = json.dumps(result.get("evidence", {}), default=str)
            db.commit()
    finally:
        db.close()

    # Keep a server-side assistant message so the requester can retrieve the
    # post-approval result from the session endpoint after approval.
    if requester_email:
        add_message(session_id, "assistant", result.get("final_answer", ""))

    return {
        "action_id": action_id,
        "status": final_status,
        "answer": result.get("final_answer", ""),
        "verified": verified,
        "execution_ok": execution_ok,
        "evidence": result.get("evidence", {}),
    }


@app.post("/approvals/{action_id}/reject")
def reject(action_id: int, req: ApprovalDecision, user: dict = Depends(current_user)):
    role_required(user, {"manager", "admin"})
    db = SessionLocal()
    try:
        row = db.get(PendingAction, action_id)
        if not row or row.status != "pending":
            raise HTTPException(status_code=404, detail="Pending action not found")
        if row.required_role == "admin" and user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin approval required")
        action = json.loads(row.payload_json)
        if action.get("_requested_by") == user["email"]:
            raise HTTPException(status_code=403, detail="A user cannot reject their own request")
        session_id = row.session_id
        row.status = "rejected"
        row.decided_by = user["email"]
        row.decided_at = __import__("datetime").datetime.utcnow()
        db.commit()
    finally:
        db.close()

    append_event(
        user["email"],
        session_id,
        "approval_decision",
        {
            "action_id": action_id,
            "decision": "rejected",
            "comment": req.comment,
            "action": action,
        },
    )
    return {"action_id": action_id, "status": "rejected", "comment": req.comment}


@app.get("/approvals/history")
def approval_history(user: dict = Depends(current_user)):
    """Return recent approved/rejected/execution-failed actions for reviewers."""
    role_required(user, {"manager", "admin"})
    db = SessionLocal()
    try:
        rows = db.execute(
            select(PendingAction)
            .where(PendingAction.status != "pending")
            .order_by(PendingAction.id.desc())
            .limit(50)
        ).scalars().all()
        return [
            {
                "id": r.id,
                "action_type": r.action_type,
                "risk_level": r.risk_level,
                "required_role": r.required_role,
                "session_id": r.session_id,
                "status": r.status,
                "payload": json.loads(r.payload_json),
                "evidence": json.loads(r.evidence_json),
                "decided_by": r.decided_by,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()

@app.get("/audit")
def audit(user: dict = Depends(current_user)):
    role_required(user, {"admin"})
    db = SessionLocal()
    try:
        rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc())).scalars().all()
        return [{"id": r.id, "ts": r.ts.isoformat(), "actor": r.actor, "session_id": r.session_id, "event_type": r.event_type, "payload": json.loads(r.payload_json), "hash": r.hash} for r in rows]
    finally:
        db.close()

@app.get("/audit/verify")
def audit_verify(user: dict = Depends(current_user)):
    role_required(user, {"admin"})
    ok, broken, msg = verify_chain()
    return {"ok": ok, "broken_row": broken, "message": msg}

@app.post("/audit/simulate-tamper")
def simulate_tamper(user: dict = Depends(current_user)):
    role_required(user, {"admin"})
    db = SessionLocal()
    try:
        row = db.execute(select(AuditLog).order_by(AuditLog.id.desc())).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="No audit row to tamper")
        row.payload_json = row.payload_json + " {\"tampered\":true}"
        db.commit()
        return {"ok": True, "tampered_row": row.id}
    finally:
        db.close()

@app.post("/data/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(current_user)):
    role_required(user, {"analyst", "manager", "admin"})
    from tempfile import NamedTemporaryFile
    from app.tools.csv_tool import profile_csv
    with NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await file.read())
        path = tmp.name
    return {"filename": file.filename, "profile": profile_csv(path)}

@app.get("/memory")
def memory(user: dict = Depends(current_user)):
    db = SessionLocal()
    try:
        rows = db.execute(select(Memory).where(Memory.user_id == int(user["sub"])).order_by(Memory.id.desc())).scalars().all()
        return [{"id": r.id, "kind": r.kind, "content": r.content, "created_at": r.created_at.isoformat()} for r in rows]
    finally:
        db.close()

@app.delete("/memory/{memory_id}")
def memory_delete(memory_id: int, user: dict = Depends(current_user)):
    db = SessionLocal()
    try:
        row = db.execute(select(Memory).where(Memory.id == memory_id, Memory.user_id == int(user["sub"]))).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Memory not found")
        db.delete(row)
        db.commit()
        return {"ok": True}
    finally:
        db.close()

@app.get("/eval/results")
def eval_results(user: dict = Depends(current_user)):
    role_required(user, {"admin"})
    db = SessionLocal()
    try:
        rows = db.execute(select(EvalResult).order_by(EvalResult.id.desc())).scalars().all()
        return [{"id": r.id, "run_at": r.run_at.isoformat(), "test_id": r.test_id, "passed": bool(r.passed), "details": json.loads(r.details_json)} for r in rows]
    finally:
        db.close()
