from __future__ import annotations

import re

EMAIL = re.compile(r"(?i)\b([a-z0-9._%+-])([a-z0-9._%+-]*)(@[a-z0-9.-]+\.[a-z]{2,})\b")
PHONE = re.compile(r"\b(?:\+?91[- .]?)?[6-9]\d{3}[- .]?\d{3}[- .]?\d{3}\b")

def mask_email(value: str) -> str:
    def repl(m):
        return f"{m.group(1)}*@{m.group(3).lstrip('@')}"
    return EMAIL.sub(repl, value)

def mask_phone(value: str) -> str:
    return PHONE.sub("****", value)

def mask_rows(rows: list[dict], role: str) -> list[dict]:
    if role in {"manager", "admin"}:
        return rows
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        for key, val in list(item.items()):
            if isinstance(val, str):
                item[key] = mask_email(mask_phone(val))
        out.append(item)
    return out
