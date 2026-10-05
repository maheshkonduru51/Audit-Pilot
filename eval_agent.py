from __future__ import annotations

import json
from datetime import datetime

from app.db.models import EvalResult
from app.db.session import SessionLocal
from app.graph.workflow import graph
from seed import seed


def run():
    seed()
    tests = json.loads(open("eval/golden_tests.json", encoding="utf-8").read())
    passed = 0
    results = []
    for t in tests:
        state = {"session_id": f"eval-{t['id']}", "user_id": 1, "user_email": "admin@jnmv.com", "role": "admin", "user_message": t["prompt"], "messages": [], "approval_status": ""}
        out = graph.invoke(state)
        ok = out.get("intent") == t.get("expected_intent")
        if "expected_risk" in t:
            ok = ok and out.get("risk", {}).get("level") == t["expected_risk"]
        results.append({"id": t["id"], "passed": ok, "intent": out.get("intent"), "risk": out.get("risk", {}).get("level"), "answer": out.get("final_answer", "")[:160]})
        passed += int(ok)
        print(f"{t['id']}: {'PASS' if ok else 'FAIL'}")
    print(f"\nPassed {passed}/{len(tests)}")
    db = SessionLocal()
    try:
        run_at = datetime.utcnow()
        for r in results:
            db.add(EvalResult(run_at=run_at, test_id=r["id"], passed=int(r["passed"]), details_json=json.dumps(r)))
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    run()
