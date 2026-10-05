# AuditPilot JNMV - Fixes Included

This full package includes the previously identified fixes and is intended to replace the earlier partial patch/full ZIP.

## 1. Approval workflow
Admin/manager approval is recorded as `approval_decision` and the approved action resumes directly through `execute -> verify -> critic -> respond` instead of starting the graph again at intent classification.

## 2. Execution and verification audit events
Executed actions write `action_executed` events and the verification node writes `verify`. Failed execution is recorded as `execution_error` and the pending-action status is updated accordingly.

## 3. Read-only refund status lookup
Questions such as "What is the current refund status for order 1317?" are routed to the read-only analytics path and no new refund approval is created.

## 4. Policy retrieval
Policy search indexes document filenames and section headings in addition to body text, with a lightweight lexical boost for exact metadata matches. Queries such as `refund approval limit` now reliably retrieve `refund_policy.md`.

## 5. Demo citation
The Demo Mode refund-window response cites `refund_policy.md / Refund window`.

## 6. Clean project package
This ZIP is the complete project, including backend, dashboard, policies, seeded-data script, evaluation suite, tests, configuration examples, and README. No virtual environment or generated SQLite database is included.
