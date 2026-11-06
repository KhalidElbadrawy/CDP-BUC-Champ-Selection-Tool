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
6. **Send assessment links.** Download a mail-merge list (name, email, personal link) and send from your mailbox. Links expire and can be replaced or cancelled.
7. **Assessments completed.** Nominees confirm consent and complete the NEXUS assessment. Follow-up questions appear on the same link when evidence is thin (up to 2 rounds). For anyone who can't use the link, enter their answers from an offline document.
8. **Review reports.** Each report shows the CV fit, the game outcome (kept separate), the evidence-linked ratings and a recommendation. Labelled AI-generated and provisional.
9. **Approve champions** with a short rationale.

The **dashboard** shows entities, champions nominated, counts per fit category and approved champions, filtered by initiative, entity and fit category, with a CSV export.

## The NEXUS game (phase 2 assessment)
Candidates choose the **NEXUS game** (recommended, laptop or tablet) or the **written version** (untimed, accessible). Once started, they cannot switch; you can reset an unfinished game after a technical problem.

- **Practice first** (untimed, not assessed), then **six rounds** restoring six districts: explore, diagnose blockers (skill gap, access, faulty equipment, policy), lay cables to connect districts to the core, and use limited energy and a small crew (Trainer, Engineer, Liaison).
- **Lasting trade-off:** fixing a district yourself is quick but builds dependency; training it costs more but lets it run independently and coach its neighbours.
- **Disruption (round 4):** new rules (Archive cables need a safety inspection) and an energy cut.
- **Requests and promises:** districts ask for help; promises are tracked to the round they're due, and players can warn about delays.
- **Co-op puzzle (round 5):** guide Kai, an AI teammate who sees information you can't. Kai is scripted, so every candidate faces the same puzzle; the player's own words are recorded.
- **Stress moments:** four timed decisions (60–90 seconds), including a senior official demanding a safety lock is switched off. If time runs out, a default consequence applies and is recorded.
- **Overall clock:** 45 minutes (Settings), multiplied by any extra time you grant a candidate.
- **Handover note** at the end: what's unfinished, who owns it, what's next.

The game runs on the server: timers and consequences can't be tampered with, and every move is saved. The AI assesses the **game record**, with every rating citing event ids (for example E23). The **game outcome** (services restored, independent districts, safety controls kept) is shown separately in the report and is never part of the score. Ratings are provisional and should be calibrated in a pilot.

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
