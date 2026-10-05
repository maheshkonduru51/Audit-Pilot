from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import Memory
from app.db.session import SessionLocal


def store_preference(user_id: int, content: str) -> None:
    db = SessionLocal()
    try:
        db.add(Memory(user_id=user_id, kind="preference", content=content, created_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()


def get_preferences(user_id: int) -> list[str]:
    db = SessionLocal()
    try:
        return [r.content for r in db.execute(select(Memory).where(Memory.user_id == user_id, Memory.kind == "preference").order_by(Memory.created_at.desc())).scalars().all()]
    finally:
        db.close()


def delete_memory(user_id: int, memory_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.execute(select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)).scalars().first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()
