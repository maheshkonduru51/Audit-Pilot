from app.audit.audit_log import append_event, verify_chain
from seed import seed

def test_audit_chain_empty_or_valid():
    seed()
    append_event("admin@jnmv.com", "test", "unit_test", {"ok": True})
    ok, broken, _ = verify_chain()
    assert ok and broken is None
