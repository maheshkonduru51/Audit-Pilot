from __future__ import annotations

from sqlalchemy import create_engine, text

from app.config import settings
from app.safety.pii_mask import mask_rows
from app.safety.sql_validator import validate_sql


def schema_text() -> str:
    return """
customers(id,name,email,phone,city,tier,created_at)
products(id,name,category,price,stock)
orders(id,customer_id,order_date,delivered_at,status,total)
order_items(id,order_id,product_id,quantity,price)
tickets(id,customer_id,order_id,subject,body,priority,status)
refunds(id,order_id,amount,reason,status,approved_by,created_at)
outbox(id,to_email,subject,body,status,created_at)
""".strip()


def run_safe_sql(sql: str, role: str) -> tuple[list[dict], str, str]:
    v = validate_sql(sql)
    if not v.ok:
        raise ValueError(v.reason)
    engine = create_engine(f"sqlite:///file:{settings.db_path.as_posix()}?mode=ro&uri=true")
    with engine.connect() as conn:
        result = conn.execute(text(v.sql))
        rows = [dict(r._mapping) for r in result.fetchall()]
    return mask_rows(rows, role), v.sql, v.reason
