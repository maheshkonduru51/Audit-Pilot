from app.tools.policy_tool import policy_search

def test_policy_has_chunks():
    assert policy_search.chunks

def test_refund_policy_retrieved():
    rows = policy_search.search("refund approval limit", 3)
    assert any("refund" in r["doc"] for r in rows)
