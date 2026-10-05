from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass
class Settings:
    company_name: str = os.getenv("COMPANY_NAME", "JNMV Overseas Pvt. Ltd.")
    llm_mode: str = os.getenv("LLM_MODE", "demo").lower().strip()
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.8-flash")
    tool_mode: str = os.getenv("TOOL_MODE", "json")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    sql_row_limit: int = int(os.getenv("SQL_ROW_LIMIT", "500"))
    session_memory_n: int = int(os.getenv("SESSION_MEMORY_N", "12"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    dashboard_api_url: str = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8000")
    db_path: Path = ROOT / "data" / "jnmv.db"
    policy_path: Path = ROOT / "data" / "policies"

settings = Settings()
