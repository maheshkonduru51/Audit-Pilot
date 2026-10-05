from app.llm.demo import DemoLLM

def test_demo_intents():
    llm=DemoLLM()
    assert llm.classify("refund order 1042") == "action"
    assert llm.classify("return window") == "policy"
    assert llm.classify("delete all customers") == "refuse_or_clarify"

def test_demo_ticket_sql():
    assert "tickets" in DemoLLM().sql("Summarise ticket 57")


def test_demo_refund_status_is_read_only():
    sql = DemoLLM().sql("What is the current refund status for order 1042?")
    assert "FROM orders o LEFT JOIN refunds r" in sql
    assert "WHERE o.id = 1042" in sql


def test_demo_refund_status_sql():
    sql = DemoLLM().sql("What is the current refund status for order 1317?")
    assert "refunds" in sql and "r.status AS refund_status" in sql

