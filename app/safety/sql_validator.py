from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from app.config import settings

ALLOWED_TABLES = {"customers", "products", "orders", "order_items", "tickets", "refunds", "outbox"}

@dataclass
class SQLValidation:
    ok: bool
    sql: str
    reason: str


def validate_sql(sql: str) -> SQLValidation:
    if not sql or not sql.strip():
        return SQLValidation(False, sql, "Empty SQL")
    normalized = sql.strip().rstrip(";")
    if ";" in normalized:
        return SQLValidation(False, sql, "Multiple statements are not allowed")
    if re.search(r"\b(PRAGMA|ATTACH|DETACH|VACUUM|DROP|DELETE|UPDATE|INSERT|ALTER|REPLACE|TRUNCATE)\b", normalized, re.I):
        return SQLValidation(False, sql, "Only read-only SELECT queries are allowed")
    try:
        statements = sqlglot.parse(normalized, read="sqlite")
    except Exception as exc:
        return SQLValidation(False, sql, f"SQL parse error: {exc}")
    if len(statements) != 1:
        return SQLValidation(False, sql, "Exactly one statement is required")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        return SQLValidation(False, sql, "Statement must be SELECT/WITH")
    tables = {t.name for t in tree.find_all(exp.Table)}
    unknown = tables - ALLOWED_TABLES
    if unknown:
        return SQLValidation(False, sql, f"Unknown tables: {sorted(unknown)}")
    if re.search(r"\bLIMIT\s+\d+\b", normalized, re.I):
        # Replace an excessive explicit limit.
        normalized = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {settings.sql_row_limit}", normalized, flags=re.I)
    else:
        normalized = f"{normalized} LIMIT {settings.sql_row_limit}"
    return SQLValidation(True, normalized, "Validated read-only SQL")
