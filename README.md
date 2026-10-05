# AuditPilot - JNMV Overseas Pvt. Ltd.

AuditPilot is a portfolio-grade enterprise workflow and data agent built from the architecture described in the supplied AuditPilot project brief. The fictional company used here is **JNMV Overseas Pvt. Ltd.** and all company data/policies are original demo data created for this project.

## What it demonstrates

- Text-to-SQL over a seeded SQLite company database
- Policy retrieval from local Markdown documents with citations
- LangGraph-controlled multi-step workflows
- Human-in-the-loop approval for risky refunds and tier changes
- SQL safety validation, PII masking, prompt-injection filtering and destructive-request blocking
- Hash-chained audit log with tamper verification
- Session memory and user preference memory
- CSV profiling and safe read-only querying
- 30-case evaluation suite
- Demo Mode (no API key) and Real Mode (Google Gemini via OpenAI-compatible endpoint)
- FastAPI backend and Streamlit dashboard

## Important API-key note

The project includes a local `.env` file for your local test setup and also includes `.env.example`. `.env` is ignored by Git.

For GitHub publication, **never commit `.env` or an API key**. Because API credentials were pasted into chat for this build, rotate the key before publishing or sharing the repository.

## Architecture

```text
User -> Streamlit -> FastAPI -> LangGraph
                           |         |
                           |         +--> SQL Tool -> SQLite (read-only)
                           |         +--> Policy Tool -> Markdown policies
                           |         +--> Action Tools -> Risk Engine
                           |         +--> Memory -> SQLite
                           |         +--> Audit Log -> SHA-256 hash chain
                           |         +--> LLM client (Demo or Gemini)
                           |
                           +--> Approval Queue -> Manager/Admin -> Execute -> Verify
```

## Windows + VS Code setup

### 1. Extract the ZIP

Extract `auditpilot.zip` and open the `auditpilot` folder in VS Code.

### 2. Create virtual environment

Use Python 3.10-3.13 on Windows. Python 3.13 is recommended for the pinned scikit-learn wheel.

PowerShell terminal:

```powershell
python --version
python -m venv venv
venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure `.env`

The ZIP already contains a local `.env` file. For a first run you can leave:

```text
LLM_MODE=demo
```

Demo Mode requires no API key.

To test Real Mode with Gemini, change:

```text
LLM_MODE=real
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-3.8-flash
```

and set your own `LLM_API_KEY` in `.env`.

### 5. Seed the database

```powershell
python seed.py
```

### 6. Start the FastAPI backend

```powershell
uvicorn app.api.main:app --reload --port 8000
```

Open:

`http://127.0.0.1:8000/docs`

### 7. Start the Streamlit dashboard

Open a second VS Code terminal, activate the virtual environment again, and run:

```powershell
venv\Scripts\Activate.ps1
python -m streamlit run dashboard\app.py
```

Open:

`http://127.0.0.1:8501`

## Demo logins

| Role | Email | Password |
|---|---|---|
| Analyst | analyst@jnmv.com | Analyst@123 |
| Manager | manager@jnmv.com | Manager@123 |
| Admin | admin@jnmv.com | Admin@123 |

## Test Demo Mode first

For a clean approval test, stop both servers and run `python seed.py` once to reset the demo database and audit log. Do not run `seed.py` again until the test is complete.

Try these prompts:

1. `Top 5 services by revenue last quarter`
2. `Customers in Hyderabad with more than 3 orders`
3. `What is the return window for travel essentials?`
4. `Refund order 1042 because the item arrived damaged`
5. `Refund order 1317 fully`
6. `Refund order 1204`
7. `Summarise ticket 57`
8. `Delete all customers older than 2 years`
9. `Remember that I prefer INR values in lakhs`
10. `What did I tell you to remember?`

Use two browser tabs to demonstrate the approval workflow: analyst in one tab, admin in the other. Order 1317 is the intended high-risk approval scenario. After the admin clicks Approve, check the response and Audit Log for `approval_decision`, `action_executed`, `verify`, `critic`, and `respond`. Then ask `What is the current refund status for order 1317?` to verify the stored refund record without creating another refund request.

## Real Mode

After Demo Mode works:

1. Stop the backend.
2. Set `LLM_MODE=real` in `.env`.
3. Make sure `LLM_API_KEY` contains a valid Gemini API key.
4. Restart the backend and dashboard.

The project uses Google's OpenAI-compatible Gemini endpoint from the `.env` configuration.

## Tests

```powershell
pytest -q
python eval_agent.py
```

The evaluation suite contains 30 cases and reports correctness, approval routing and seeded-attack success rate.

## GitHub safety

Before running Git commands:

```powershell
# Verify the secret is ignored
git status --ignored
```

Do not remove `.env` from `.gitignore`. For GitHub, publish `.env.example` only.

## Troubleshooting

- `python is not recognized`: reinstall Python and tick Add Python to PATH.
- `Activate.ps1 cannot be loaded`: use the Set-ExecutionPolicy command above.
- `ModuleNotFoundError: app`: run commands from the project root.
- `401`: verify the Gemini key and base URL in `.env`.
- `429`: wait for the provider rate limit or switch temporarily to Demo/Ollama.
- `Model not found`: check the current Gemini model name in Google AI Studio and update `LLM_MODEL`.
- Port 8000 busy: use `--port 8001` and update `DASHBOARD_API_URL`.
- Unicode error on Windows: `$env:PYTHONUTF8=1`.

## Resume-ready description

> Built AuditPilot, an enterprise workflow agent using LangGraph, FastAPI and SQLite that answers data questions with validated text-to-SQL, grounds policy answers in cited documents, and executes controlled business workflows with role-based approval gates.
>
> Added SQL safety, PII masking, prompt-injection defenses, tamper-evident audit logging, persistent memory, verification steps and a 30-case evaluation suite.

## Source basis

This build follows the supplied AuditPilot project brief: enterprise workflow/data agent, LangGraph graph, SQL safety, policy retrieval, approval gates, audit chain, memory, evaluation and Demo/Real LLM modes.
