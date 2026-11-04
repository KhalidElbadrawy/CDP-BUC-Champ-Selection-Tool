# CDP Champion Nomination Tool (MVP)

A working MVP for nominating, assessing, and appointing **Business User Champions** for the Common Digital Platforms across ~55 government entities.

- **Stack:** Python 3.11+, FastAPI, Jinja (server-rendered, no JavaScript build), SQLite, and the **Claude Agent SDK** for server-side AI assessment.
- **Access:** secure, expiring, revocable email links. No accounts or passwords.
- **Assessment:** fully automated: CV screening, then **two blinded AI passes**, then an **AI moderator**, then **scores calculated in code**.
- **Languages:** English and Arabic (RTL). Accessible, mobile-friendly government styling.

> All demo records are fictional. With no API key configured, assessments come from a clearly labelled **SIMULATED** rule-based assessor.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env              # optional; demo mode works without it
.venv/bin/python -m app.seed      # loads fictional demo data (resets the local DB)
.venv/bin/uvicorn app.main:app --reload
```

Open http://localhost:8000/demo. In demo mode this launcher stands in for opening emailed links, so you can enter any role.

Run the validation suite:

```bash
.venv/bin/python -m pytest -q
```

## Going live

| Setting | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` + `CDP_AI_MODE=live` | Live AI assessment through the Claude Agent SDK. Get a key at https://console.anthropic.com/. The key is read on the server only. |
| `CDP_MODEL` | Model used for screening, assessment passes, and moderation (default `claude-sonnet-5-5`). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Real email delivery. Without them, emails go to the **Outbox** (`/lead/outbox`), marked `demo-logged`. |
| `CDP_BASE_URL` | Public HTTPS URL used in emailed links. Use HTTPS in production so cookies are `Secure`. |
| `CDP_SECRET_KEY`, `CDP_LEAD_EMAIL` | CSRF signing key; the CDP Change Lead's address (used to request the central dashboard link at `/access`). |

When SMTP is configured, the demo launcher switches off automatically (or set `CDP_DEMO_LAUNCHER=0`). Schedule `POST /lead/jobs` (or the "Run scheduled jobs" button) daily. It retries failed assessments, sends due reminders, and applies the retention policy.

## Walkthrough

### 1. CDP Change Lead launches a round
1. Request the central link at `/access` using `CDP_LEAD_EMAIL`.
2. **Settings:** launch a nomination round. Review the scorecard weights (must total 100), the 70/100 threshold, the minimum ratings (empathy, reliability, judgment ≥ 3), clarification rounds, reminder limits, link expiry, and retention. Every save creates a new **configuration version**, and each assessment records the version it used.
3. **Entities:** for each entity, set nomination targets and coverage priorities (platforms, workflows, user groups, locations, capacity), and assign **focal points** and **sponsors** centrally. "Email dashboard link" sends them their scoped link.
4. **Email templates:** edit and preview every message, and choose which ones focal points may trigger as approved reminders.

### 2. Entities support their nominees
- A focal point opens **/entity**. They copy the entity's shared nomination link (it shows only the role description and form, never existing nominations) or email the role announcement.
- The dashboard shows only their entity: targets, nominees, statuses, outstanding actions with owner and due date, reminder history, and **outcome summaries only**. CVs, evidence, and ratings stay hidden, and focal points cannot change anything about an assessment.
- **Send reminder** / **Resend link** sends the approved template for the current stage. Duplicate or excessive reminders are blocked (minimum gap, maximum per stage). Withdrawn nominees never get reminders.

### 3. Nomination, consent, application
- Self, peer, and manager nominations all go through `/n/<entity>`. **Duplicate detection:** a second nomination of the same email in a round is recorded against the existing record, and the response is identical so nothing leaks.
- Every nominee receives a personal emailed link. Opening it proves email ownership. **Consent is required** before any CV is uploaded or anything is assessed.
- Application steps: CV upload (PDF/DOCX; unreadable, scanned, encrypted, or oversized files are handled explicitly); a CV extraction summary the nominee **reviews and corrects**; the six scorecard tasks, including a **simulated coaching exchange** and a **structured workflow walkthrough**; targeted follow-up questions generated from the CV; and availability and protected hours. The nominee can save and resume at any time.

### 4. Automated assessment (no human scoring or moderation)
1. **Evidence snapshot:** on submission, an immutable, versioned snapshot is built. Names, emails, phones, links, and personal-characteristic lines (age, gender, DOB, nationality and similar) are redacted. Every item is source-tagged and wrapped as `<candidate_evidence>` **data**. Embedded instructions are ignored and flagged.
2. **Two blinded passes (A and B):** separate, tool-less Agent SDK sessions run in parallel on the same snapshot, rubric, and rules. Neither sees the other's output. Each returns criterion ratings (or *Not yet assessed*), excerpts with source IDs, reasoning, evidence strength, missing evidence, contradictions, and unsafe flags.
3. **Moderator:** compares the passes. It confirms agreement, **re-evaluates** differences against the rubric (never averages), requests targeted **clarification**, or assigns an approved **remediation exercise** for unsafe responses. Every difference and its resolution goes to the audit trail.
4. **Scoring in code** (`app/scoring.py`): weighted points = (rating ÷ 5) × weight. Totals appear only when every criterion is assessed. Otherwise results show as partial, e.g. "52 points from 65 assessed points; 35 points remain unassessed." The code then applies the threshold and minimums, and any serious unsafe response means remediation regardless of total.
5. **Up to 2 clarification/reassessment rounds** happen automatically. If evidence is still insufficient, the result is "Incomplete—additional evidence required."
6. All outputs are labelled **AI-generated** (or **SIMULATED** in demo). Agreement between passes shows scoring consistency; it does not verify CV claims.

If the AI service fails, the submission is kept, the status returns to *Submitted* with a visible note, and the scheduled job or the Lead's **Retry** reruns the assessment.

### 5. Appointment requirements
- **Meets thresholds:** the nominee confirms continued willingness, and the line manager confirms protected hours, workload, availability, and **required access** using `/manager` (they see only role requirements, never the evidence).
- When all of those are confirmed, the **sponsor** (`/sponsor`) sees summaries, the requirements checklist, and coverage fit, shown separately from assessment quality. The sponsor records a decision with a rationale, the coverage need, a **conflict-of-interest declaration**, and any conditions. The server blocks a provisional appointment unless consent, the assessment, capacity, access, and willingness are all met.
- **Provisionally appointed:** the nominee accepts the versioned role charter. The programme team assigns a buddy, completes the onboarding checklist, and sets the initial workflow objective and start date. The day-90 date is calculated automatically.
- **Day 90:** the nominee and manager submit readiness, contribution, workload, and willingness. The sponsor then records **confirmed**, **extended** (re-review in 60 days), or **concluded**.
- **Does not meet:** the Lead sends a respectful outcome message. The nominee sees the explanation and can **request reconsideration**; the Lead can reopen the application.

## Security and data handling
- Link tokens are 256-bit random values stored only as SHA-256 hashes. Each is scoped to a role and to one entity or application, expires (configurable per role), and can be revoked. Removing a contact revokes their links. **Request a fresh link** at `/access` always gives the same response.
- Permissions are checked on the server for every route and record. Cross-scope access returns 404, so a record's existence isn't revealed. Forms carry an HMAC CSRF token, and cookies are HttpOnly and SameSite=Lax.
- CVs and detailed evidence are visible only to the nominee and the CDP Change Lead. Anyone else needs an explicit, audited **access grant** from the Lead. Every document view is audited.
- Emails contain a link and minimal personal data, never CV or assessment content.
- **Retention:** closed records older than the configured period have their CV files and evidence snapshots deleted. Results and the audit trail are kept. Per-record deletion is also available.
- The audit trail covers scores, moderation differences, configuration changes, communications (with delivery status), decisions, access, and exports.

## Project layout
```
app/
  scoring.py     scorecard, weights, thresholds, versioned config (pure code)
  ai.py          Agent SDK live engine + labelled demo engine, schemas, guardrails
  workflow.py    statuses, gates, assessment orchestration, next action / owner / due
  security.py    passwordless role-scoped links, permission checks, CSRF
  emails.py      editable templates, SMTP/outbox delivery, reminder throttling
  extraction.py  PDF/DOCX extraction, unreadable handling, redaction
  main.py        routes for the six screen types
  seed.py        fictional demo data
  templates/     Jinja templates (EN/AR, RTL)
tests/test_mvp.py  validation checklist
```

## Later enhancements (out of MVP scope)
Recognition badges, advanced analytics, calendar integration, learning-platform integration, a full Arabic translation of the email templates, PostgreSQL plus object storage for production, and a job queue for assessments.
