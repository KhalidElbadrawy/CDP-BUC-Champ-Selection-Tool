"""Production safety lock and built-in daily job scheduler.

Set CDP_ENV=production on a public server. The app then refuses to serve anything
(except a setup checklist) until live AI, the Change Lead's password, a secret key and an
HTTPS address are configured. Demo data and the demo password are never available there.
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
    if len(s.lead_password) < 10:
        problems.append("CDP_LEAD_PASSWORD is missing or shorter than 10 characters: choose the Change Lead's sign-in password.")
    if not os.environ.get("CDP_SECRET_KEY"):
        problems.append("CDP_SECRET_KEY is missing: set it to a long random value.")
    if not s.base_url.startswith("https://"):
        problems.append("CDP_BASE_URL must be the app's public https:// address (for example https://your-app.onrender.com).")
    return problems


async def scheduler_loop() -> None:
    """Run the scheduled jobs (assessment retries, retention) every CDP_JOBS_EVERY_HOURS hours."""
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
