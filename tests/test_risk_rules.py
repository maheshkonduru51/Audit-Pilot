from app.safety.risk_rules import assess

def test_small_refund_auto():
    d = assess("refund", 1900, True)
    assert d.auto_execute and not d.blocked

def test_medium_refund_manager():
    d = assess("refund", 5000, True)
    assert d.required_role == "manager"

def test_large_refund_admin():
    d = assess("refund", 30000, True)
    assert d.required_role == "admin"

def test_bulk_delete_blocked():
    d = assess("delete", row_count=20)
    assert d.blocked
