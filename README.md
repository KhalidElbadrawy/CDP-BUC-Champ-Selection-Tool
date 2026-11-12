# CDP Champion Selection (version 2)

A tool for the **CDP Change Lead** to select Business User Champions for each platform initiative.

- **One user:** the CDP Change Lead signs in with a password. Nominees use only a personal assessment link.
- **No email sending and no internal integration:** nominations come from your own survey tool; you send assessment links from your own mailbox.
- **Initiatives:** each platform release runs the same 9-step flow, with a step tracker you mark complete.
- **AI:** CV fit screening (High / Moderate / Low / Doesn't Fit), then a behavioural assessment rated by two independent AI assessments and an AI moderator. Scores are calculated in code.

Version 1 (the multi-role nomination tool) is kept on the `v1` and `main` branches.

## The 9 steps (per initiative)
1. **Collect nominations** in your survey tool (for example Microsoft Forms). Include a question confirming the nominee agreed to AI screening of their CV.
2. **Import survey results** (Excel or CSV). Match the columns once; the tool remembers them. Duplicates are skipped; nominees without consent are marked *No Consent* and never screened.
3. **Upload CVs** in bulk (PDF or DOCX). Files are matched by the nominee's name in the file name; assign any that don't match.
4. **AI fit rating.** High and Moderate Fit are shortlisted automatically. A CV shows experience, not behaviour, so this is screening only.
5. **Review shortlist.** Change any fit category with a recorded reason.
6. **Send assessment links.** Press **Invite** next to a shortlisted nominee to email them their personal link (in English and Arabic), or download a mail-merge list (name, email, personal link) and send from your mailbox. Links expire and can be replaced or cancelled.
7. **Assessments completed.** Nominees confirm consent and complete the LAUNCH WINDOW assessment. Follow-up questions appear on the same link when evidence is thin (up to 2 rounds). For anyone who can't use the link, enter their answers from an offline document.
8. **Review reports.** Each report shows the CV fit, the game outcome (kept separate), the evidence-linked ratings and a recommendation. Labelled AI-generated and provisional.
9. **Approve champions** with a short rationale.

The **dashboard** shows entities, champions nominated, counts per fit category and approved champions, filtered by initiative, entity and fit category, with a CSV export.

## LAUNCH WINDOW (phase 2 assessment)
Candidates choose **LAUNCH WINDOW** (recommended, laptop or tablet with sound) or the **written version** (untimed, accessible, same story). Once started, they cannot switch; you can reset an unfinished game after a technical problem.

LAUNCH WINDOW is a role-playing game in English or Arabic. The candidate joins the crew of a fictional launch base for the last hour before a launch. The game never mentions champions or the candidate's job: each scene is built so the six behaviours show up naturally.

| Scene | What the candidate does | Mainly reveals |
|---|---|---|
| Prologue | Opening cinematic; walk to the briefing hall (tutorial, not assessed) | — |
| Act I · Briefing (3-minute clock) | Open up to 4 of 8 mission files, answer 3 readiness checks (with an honest "I'm not sure, I'd check" option) | Curiosity, process thinking |
| Act II · Crew rounds | Coach Noor, a nervous rookie, through her first check; answer 5 crew calls by fixing, teaching, routing or promising | Peer influence, empathy, routing |
| Act III · Anomaly (timed waves) | Triage alerts: handle, send a crew member or route to the owning station; the Flight Director orders a safety-lock override | Judgment, escalation, priorities |
| Act IV · Final checks | Guide Hamad by radio (he sees the panel, you see the manual); then deliver, warn early or let promises slip | Empathy, curiosity, reliability |
| Epilogue | Choose 3 actions for the next shift, write a handover note, watch the launch | Peer influence, reliability |
| After the game | Two short questions about the candidate's real work | Real examples, business workflow knowledge |

- Choices made earlier pay off later: a colleague you taught handles an alert without you; one you only fixed things for calls you again in the middle of the emergency.
- Players can pick a reply or type their own words; their words are kept for the AI.
- Voices (male narrator, cast of five), music and sound effects were generated with ElevenLabs and are stored in `app/static/launch/`. Captions are always on, and sound can be switched off.
- Timed moments scale with any extra time you grant a candidate. The overall limit is in Settings (default 45 minutes).

The game runs on the server: timers can't be tampered with, and every choice is saved as an event. The AI assesses the **game record** plus the two real-work answers, with every rating citing event ids (for example E23). Trust, readiness, rank and the launch ending are the **game outcome**: shown separately in the report and never part of the score. Ratings are provisional and should be calibrated in a pilot.

## Inviting nominees by email
Each shortlisted nominee has an **Invite** button (on the initiative's nominee table and on their own page). It creates a fresh personal link and emails it to the nominee's address from the survey, in English and Arabic. **Resend** sends a new link; the earlier one stops working once the new email is delivered. If sending fails, nothing changes: their earlier link, if any, still works, and the error is shown. Each nominee's page lists the invitations sent and shows the latest email; the stored copy has the link shortened, because working links are never kept.

Sending needs a mailbox the tool can sign in to. Add these in Render's **Environment** (never in GitHub): `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `CDP_LEAD_EMAIL` for replies. For Microsoft 365 use `smtp.office365.com`; your IT team may need to allow SMTP sign-in for that mailbox. **Settings → Email** shows whether email is set up and can send a test message. Without these settings, production switches the Invite buttons off; locally (demo) Invite saves the email on the nominee's page without sending it.

## Clearing data
On each initiative's page, **Clear stored data** permanently deletes that initiative's nominee records: survey rows, CV files, AI ratings, answers, game records, links, decisions and their audit entries. Type the initiative's name to confirm. You can keep the initiative (its steps reset) or delete it too. Other initiatives are untouched.

## Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed          # fictional demo data + samples/nominations_sample.csv
.venv/bin/uvicorn app.main:app
```
Open http://localhost:8000 and sign in with the password **demo** (only when `CDP_LEAD_PASSWORD` is not set and not in production). Try importing `samples/nominations_sample.csv` into the "HR Self-Service Rollout" initiative. Hassan Ali's report shows a completed game; Noor Jaber is part-way through one.

Tests: `.venv/bin/python -m pytest -q`

## Publish (Render)
`render.yaml` sets up the server, a persistent disk and the daily jobs. In Render choose **New → Blueprint**, select this repository and the `v2` branch, and enter `ANTHROPIC_API_KEY`, `CDP_LEAD_PASSWORD` and `CDP_BASE_URL` (your `https://…onrender.com` address). Until all are set, the site shows only a *Setup incomplete* checklist. Never run `app.seed` on the server.

## Data handling
CVs and answers are visible only to the signed-in Change Lead. Personal identifiers are removed before AI processing, and candidate material is treated as data, never as instructions. Every import, AI rating, override, link, assessment, decision and settings change is in the audit trail. CVs of closed records are deleted after the retention period.
