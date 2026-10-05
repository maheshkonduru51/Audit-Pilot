from app.safety.sql_validator import validate_sql

def test_select_allowed():
    r = validate_sql("SELECT * FROM customers")
    assert r.ok and "LIMIT 500" in r.sql

def test_delete_blocked():
    assert not validate_sql("DELETE FROM customers").ok

def test_drop_blocked():
    assert not validate_sql("DROP TABLE customers").ok

def test_multiple_statements_blocked():
    assert not validate_sql("SELECT * FROM customers; SELECT * FROM orders").ok

def test_unknown_table_blocked():
    assert not validate_sql("SELECT * FROM secrets").ok
