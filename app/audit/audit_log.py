from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.models import AuditLog
from app.db.session import SessionLocal


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def append_event(actor: str, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        last = db.execute(select(AuditLog).order_by(AuditLog.id.desc())).scalars().first()
        prev_hash = last.hash if last else "0" * 64
        ts = datetime.utcnow()
        payload_json = _canonical(payload)
        digest = hashlib.sha256(f"{prev_hash}{ts.isoformat()}{actor}{event_type}{payload_json}".encode("utf-8")).hexdigest()
        db.add(AuditLog(ts=ts, actor=actor, session_id=session_id, event_type=event_type, payload_json=payload_json, prev_hash=prev_hash, hash=digest))
        db.commit()
    finally:
        db.close()


def verify_chain() -> tuple[bool, int | None, str]:
    db = SessionLocal()
    try:
        rows = db.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
        prev = "0" * 64
        for row in rows:
            expected = hashlib.sha256(f"{prev}{row.ts.isoformat()}{row.actor}{row.event_type}{row.payload_json}".encode("utf-8")).hexdigest()
            if row.prev_hash != prev or row.hash != expected:
                return False, row.id, "Audit chain verification failed"
            prev = row.hash
        return True, None, "Audit chain verified"
    finally:
        db.close()
