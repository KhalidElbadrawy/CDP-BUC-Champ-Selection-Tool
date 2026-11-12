"""Sends email through the mail server named in the hosting settings.

Settings (Render > Environment, or a local .env; never in GitHub):
  SMTP_HOST      e.g. smtp.office365.com (Microsoft 365) or smtp.gmail.com
  SMTP_PORT      587 (STARTTLS, the usual choice) or 465 (SSL)
  SMTP_USER      the mailbox that sends, e.g. cdp-champions@your-org.gov
  SMTP_PASSWORD  that mailbox's password or app password
  SMTP_FROM      the address shown as the sender (usually the same mailbox)
  CDP_LEAD_EMAIL replies go here

Without SMTP_HOST, email is not set up: outside production the tool records invitations in its
outbox without sending them (demo), and in production it refuses to pretend an invite was sent.
"""
from __future__ import annotations

import asyncio
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app import config

SENDER_NAME = "CDP Champion Programme"


class MailError(Exception):
    """Sending failed. The message is safe to show: it never contains the password."""


def configured() -> bool:
    return bool(config.settings.smtp_host)


def reply_to() -> str | None:
    lead = config.settings.lead_email
    return lead if lead and not lead.endswith("@example.gov") else None


def summary() -> dict:
    s = config.settings
    return {"configured": configured(), "host": s.smtp_host, "port": s.smtp_port, "sender": s.smtp_from,
            "reply_to": reply_to(), "user_set": bool(s.smtp_user)}


def _deliver(msg: EmailMessage) -> None:
    s = config.settings
    ctx = ssl.create_default_context()
    try:
        if s.smtp_port == 465:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=30, context=ctx)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
        with server:
            if s.smtp_port != 465 and s.smtp_starttls:
                server.starttls(context=ctx)
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailError("The mail server refused the sign-in. Check SMTP_USER and SMTP_PASSWORD.") from None
    except smtplib.SMTPRecipientsRefused:
        raise MailError("The mail server refused the recipient's address.") from None
    except smtplib.SMTPSenderRefused:
        raise MailError("The mail server refused the sender address. Check SMTP_FROM.") from None
    except (socket.timeout, TimeoutError):
        raise MailError("The mail server did not answer in time.") from None
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"The mail server could not be reached or refused the message ({type(e).__name__}).") from None


async def send(to: str, subject: str, text: str, html: str) -> None:
    s = config.settings
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((SENDER_NAME, s.smtp_from))
    msg["To"] = to
    if reply_to():
        msg["Reply-To"] = reply_to()
    msg["Message-ID"] = make_msgid(domain=s.smtp_from.split("@")[-1] if "@" in s.smtp_from else None)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    await asyncio.to_thread(_deliver, msg)
