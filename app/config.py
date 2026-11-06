"""Runtime settings, read from environment variables (see .env.example).

Credentials (Anthropic API key, SMTP password) are only ever read on the server.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader so the app runs without extra dependencies."""
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


class Settings:
    def __init__(self) -> None:
        _load_dotenv()
        e = os.environ.get
        self.db_path = str(BASE_DIR / e("CDP_DB", "data/cdp.sqlite3")) if not os.path.isabs(e("CDP_DB", "")) else e("CDP_DB")
        self.upload_dir = str(BASE_DIR / e("CDP_UPLOAD_DIR", "data/uploads")) if not os.path.isabs(e("CDP_UPLOAD_DIR", "")) else e("CDP_UPLOAD_DIR")
        self.base_url = e("CDP_BASE_URL", "http://localhost:8000").rstrip("/")
        self.lead_email = e("CDP_LEAD_EMAIL", "change.lead@example.gov").lower()
        self.secret_key = e("CDP_SECRET_KEY") or self._dev_secret()

        api_key = e("ANTHROPIC_API_KEY", "")
        has_key = bool(api_key) and api_key != "your_api_key_here"
        requested = e("CDP_AI_MODE", "demo").lower()
        self.ai_mode = "live" if (requested == "live" and has_key) else "demo"
        self.ai_mode_reason = (
            "Live AI assessment enabled." if self.ai_mode == "live"
            else ("CDP_AI_MODE=live was requested but ANTHROPIC_API_KEY is missing."
                  if requested == "live" else "CDP_AI_MODE is not set to 'live'.")
        )
        self.model = e("CDP_MODEL", "claude-sonnet-5-5")

        self.lead_password = e("CDP_LEAD_PASSWORD", "")
        self.smtp_host = e("SMTP_HOST", "")
        self.smtp_port = int(e("SMTP_PORT", "587") or 587)
        self.smtp_user = e("SMTP_USER", "")
        self.smtp_password = e("SMTP_PASSWORD", "")
        self.smtp_from = e("SMTP_FROM", "cdp-champions@example.gov")
        self.smtp_starttls = e("SMTP_STARTTLS", "true").lower() == "true"
        self.email_mode = "live" if self.smtp_host else "demo"

    def _dev_secret(self) -> str:
        path = Path(self.db_path).parent / ".secret"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(secrets.token_hex(32))
        return path.read_text().strip()


settings = Settings()


def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
