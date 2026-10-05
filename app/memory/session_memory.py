from __future__ import annotations

from collections import deque

SESSIONS: dict[str, deque[dict[str, str]]] = {}


def add_message(session_id: str, role: str, content: str, limit: int = 12) -> None:
    q = SESSIONS.setdefault(session_id, deque(maxlen=limit))
    q.append({"role": role, "content": content})


def get_messages(session_id: str) -> list[dict[str, str]]:
    return list(SESSIONS.get(session_id, []))
