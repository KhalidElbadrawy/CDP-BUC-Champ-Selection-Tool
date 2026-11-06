"""Production safety lock and built-in daily job scheduler.

Set CDP_ENV=production on a public server. The app then refuses to serve anything
(except a setup checklist) until live AI, real email, a secret key, the Change Lead's
email and an HTTPS address are configured, and the demo launcher is always off.
"""
from __future__ import annotations

import asyncio
import logging
import os

from app import config

log = logging.getLogger("cdp")


def is_production() -> bool:
    return os.environ.get("CDP_ENV", "").lower() == "production"


def setup_problems() -> list[str]:
    """Plain-language list of missing settings. Never includes secret values."""
    if not is_production():
        return []
    s = config.settings
    problems = []
    if s.ai_mode != "live":
        problems.append("ANTHROPIC_API_KEY is missing (and CDP_AI_MODE must be 'live'): add your Anthropic API key.")
    if s.email_mode != "live":
        problems.append("SMTP_HOST is missing: add your email server settings (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM).")
    if not os.environ.get("CDP_SECRET_KEY"):
        problems.append("CDP_SECRET_KEY is missing: set it to a long random value.")
    if not os.environ.get("CDP_LEAD_EMAIL") or s.lead_email == "change.lead@example.gov":
        problems.append("CDP_LEAD_EMAIL is missing: set it to the CDP Change Lead's work email.")
    if not s.base_url.startswith("https://"):
        problems.append("CDP_BASE_URL must be the app's public https:// address (for example https://your-app.onrender.com).")
    return problems


async def scheduler_loop() -> None:
    """Run the scheduled jobs (retries, reminders, retention) every CDP_JOBS_EVERY_HOURS hours."""
    from app.main import run_jobs
    hours = float(os.environ.get("CDP_JOBS_EVERY_HOURS", "0") or 0)
    if hours <= 0:
        return
    await asyncio.sleep(120)  # let the app finish starting
    while True:
        if not setup_problems():
            try:
                log.info("Scheduled jobs: %s", await run_jobs("scheduler"))
            except Exception:  # never let the loop die
                log.exception("Scheduled jobs failed")
        await asyncio.sleep(hours * 3600)
