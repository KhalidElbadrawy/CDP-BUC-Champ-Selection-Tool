"""Email templates, delivery (SMTP or demo outbox) and reminder throttling.

Emails carry a secure link and minimal personal information. CVs and assessment evidence
are never attached or quoted; recipients open the tool to see anything private.
"""
from __future__ import annotations

import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from string import Formatter

from app import config, db

DEFAULT_TEMPLATES: dict[str, dict] = {
    "announcement": dict(focal=1,
        subject="Become a CDP Business User Champion — {entity}",
        body="Hello,\n\n{entity} is nominating Business User Champions to help colleagues adopt the Common Digital "
             "Platforms. Champions give a few protected hours a month to coach colleagues, share tips and raise "
             "issues.\n\nRead the role description and nominate yourself or a colleague here:\n{link}\n\n"
             "CDP Change Team"),
    "consent_request": dict(focal=1,
        subject="You have been nominated as a CDP Champion",
        body="Hello {nominee_name},\n\nYou have been nominated to become a CDP Business User Champion for {entity}. "
             "Nothing about you will be assessed unless you agree.\n\nPlease review the role and give or decline "
             "consent here (personal link, expires {expires}):\n{link}\n\nReference: {ref}"),
    "acknowledgment": dict(focal=0,
        subject="Application received — {ref}",
        body="Hello {nominee_name},\n\nThank you. Your CDP Champion application {ref} has been submitted and "
             "automated assessment has started. You can check progress at any time:\n{link}"),
    "application_link": dict(focal=1,
        subject="Your CDP Champion application link",
        body="Hello {nominee_name},\n\nUse this personal link to continue your application (expires {expires}):\n{link}\n\n"
             "Your progress is saved automatically when you select Save."),
    "clarification": dict(focal=1,
        subject="Additional evidence requested — {ref}",
        body="Hello {nominee_name},\n\nTo complete your assessment we need a little more information. Please open "
             "your application and answer the follow-up questions:\n{link}\n\nPlease respond by {due}."),
    "reassessment": dict(focal=1,
        subject="Short reassessment exercise — {ref}",
        body="Hello {nominee_name},\n\nPlease complete a short exercise so we can finish your assessment:\n{link}\n\n"
             "Please respond by {due}."),
    "outcome_meets": dict(focal=0,
        subject="Your CDP Champion assessment — next steps",
        body="Hello {nominee_name},\n\nYour assessment meets the proposed thresholds. Next, your line manager will be "
             "asked to confirm protected time, and you will be asked to confirm you still wish to take part:\n{link}"),
    "manager_request": dict(focal=1,
        subject="Please confirm capacity for a CDP Champion nominee",
        body="Hello {manager_name},\n\n{nominee_name} is progressing as a CDP Business User Champion for {entity}. "
             "Please confirm protected hours, workload arrangements, availability and required access using this "
             "short form (expires {expires}):\n{link}\n\nPlease respond by {due}."),
    "sponsor_request": dict(focal=1,
        subject="CDP Champion appointment decision needed — {entity}",
        body="Hello,\n\nOne or more CDP Champion candidates for {entity} are ready for your provisional appointment "
             "decision. Review the summaries and record your decision here (expires {expires}):\n{link}"),
    "provisional_appointment": dict(focal=0,
        subject="Provisional appointment as CDP Champion",
        body="Hello {nominee_name},\n\nCongratulations — you have been provisionally appointed as a CDP Business "
             "User Champion for {entity}. Please review and accept the role charter:\n{link}"),
    "onboarding": dict(focal=1,
        subject="CDP Champion onboarding actions",
        body="Hello {nominee_name},\n\nWelcome aboard. Your onboarding checklist and buddy details are ready:\n{link}"),
    "day90": dict(focal=1,
        subject="Your CDP Champion day-90 review",
        body="Hello {recipient_name},\n\nIt is time for the day-90 review for {nominee_name}. Please complete the short "
             "review form (expires {expires}):\n{link}"),
    "unsuccessful": dict(focal=0,
        subject="Your CDP Champion application",
        body="Hello {nominee_name},\n\nThank you for applying to become a CDP Business User Champion and for the time "
             "you put into your application. On this occasion we are not able to offer an appointment. You can view "
             "a short explanation and request reconsideration here:\n{link}\n\nYour interest in helping colleagues is "
             "valued, and we hope you will consider future rounds."),
    "access_link": dict(focal=0,
        subject="Your CDP Champion access link",
        body="Hello,\n\nHere is your requested access link for the CDP Champion tool (expires {expires}):\n{link}\n\n"
             "If you did not request this, you can ignore this email."),
    "withdrawal": dict(focal=0,
        subject="Withdrawal confirmed — {ref}",
        body="Hello {nominee_name},\n\nYour withdrawal from the CDP Champion process has been recorded. No further "
             "assessment will take place and no further reminders will be sent."),
}
# Which template is the "approved reminder" for each status (used by focal-point reminders).
REMINDER_FOR_STATUS = {
    "Nominated": ("consent_request", "nominee"),
    "Awaiting Consent": ("consent_request", "nominee"),
    "Application in Progress": ("application_link", "nominee"),
    "Awaiting Evidence": ("clarification", "nominee"),
    "Reassessment Required": ("reassessment", "nominee"),
    "Awaiting Manager Commitment": ("manager_request", "manager"),
    "Provisionally Appointed": ("provisional_appointment", "nominee"),
    "Onboarding": ("onboarding", "nominee"),
}
ALLOWED_WHEN_WITHDRAWN = {"withdrawal", "access_link"}


def seed_templates() -> None:
    for key, t in DEFAULT_TEMPLATES.items():
        if not db.q1("SELECT 1 FROM email_templates WHERE key=?", (key,)):
            db.ex("INSERT INTO email_templates(key, subject_en, body_en, focal_may_send, updated_at) VALUES (?,?,?,?,?)",
                  (key, t["subject"], t["body"], t["focal"], db.now()))


class _Safe(dict):
    def __missing__(self, key):
        return ""


def render(key: str, ctx: dict) -> tuple[str, str]:
    t = db.q1("SELECT * FROM email_templates WHERE key=?", (key,))
    if not t:
        raise KeyError(key)
    f = Formatter()
    return f.vformat(t["subject_en"], (), _Safe(ctx)), f.vformat(t["body_en"], (), _Safe(ctx))


def _deliver(to: str, subject: str, body: str) -> tuple[str, str | None]:
    s = config.settings
    if s.email_mode == "demo":
        return "demo-logged", None
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return "sent", None
    except Exception as e:
        return "failed", f"{type(e).__name__}: {e}"


def reminder_block_reason(application: dict, template: str) -> str | None:
    """Prevent duplicate or excessive reminders. Returns a reason string if blocked."""
    from app.scoring import current_config
    rules = current_config()[1]["reminders"]
    if application.get("withdrawn_at"):
        return "Application withdrawn — reminders stopped."
    since = application["status_changed_at"]
    rows = db.q("SELECT created_at FROM emails WHERE application_id=? AND template=? AND is_reminder=1 "
                "AND status IN ('sent','demo-logged') AND created_at>=? ORDER BY created_at DESC",
                (application["id"], template, since))
    if len(rows) >= int(rules["max_per_stage"]):
        return f"Maximum of {rules['max_per_stage']} reminders for this stage already sent."
    last = db.q1("SELECT created_at FROM emails WHERE application_id=? AND template=? AND status IN ('sent','demo-logged') "
                 "ORDER BY created_at DESC LIMIT 1", (application["id"], template))
    if last:
        gap = datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])
        if gap < timedelta(hours=float(rules["min_hours_between"])):
            return f"A message was sent less than {rules['min_hours_between']} hours ago."
    return None


def send(key: str, to: str, ctx: dict, *, application: dict | None = None, entity_id: int | None = None,
         is_reminder: bool = False, triggered_by: str = "system") -> dict:
    app_id = application["id"] if application else None
    if application and application.get("withdrawn_at") and key not in ALLOWED_WHEN_WITHDRAWN:
        status, err, subject, body = "suppressed", "Application withdrawn", key, ""
    else:
        subject, body = render(key, ctx)
        block = reminder_block_reason(application, key) if (is_reminder and application) else None
        if block:
            status, err = "suppressed", block
        else:
            status, err = _deliver(to, subject, body)
    eid = entity_id or (application["entity_id"] if application else None)
    mid = db.ex("INSERT INTO emails(application_id, entity_id, template, to_email, subject, body, is_reminder, status, error, triggered_by, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (app_id, eid, key, to, subject, body, int(is_reminder), status, err, triggered_by, db.now()))
    db.audit("email." + status, actor_role=triggered_by.split(":")[0], application_id=app_id, entity_id=eid,
             template=key, to=to, error=err)
    return {"id": mid, "status": status, "error": err}
