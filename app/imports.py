"""Survey import: read a CSV or Excel export (e.g. Microsoft Forms) and map its columns to fields."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

FIELDS: list[tuple[str, str, bool]] = [
    # key, label, required
    ("name", "Nominee name", True),
    ("email", "Nominee work email", False),
    ("entity", "Entity", True),
    ("department", "Department", False),
    ("platform", "Platform", False),
    ("workflow", "Business workflow", False),
    ("route", "Nomination route (self / peer / manager)", False),
    ("nominator_name", "Nominator name", False),
    ("nominator_email", "Nominator email", False),
    ("reason", "Reason for nomination", False),
    ("manager_name", "Line manager name", False),
    ("manager_email", "Line manager email", False),
    ("consent", "Nominee consent to AI screening", False),
]
FIELD_KEYS = [f[0] for f in FIELDS]

# Most specific phrases first. Microsoft Forms' own "Name"/"Email" columns are the respondent (nominator).
HINTS: dict[str, list[str]] = {
    "name": ["nominee name", "name of nominee", "name of the nominee", "champion name", "candidate name", "nominee's name", "اسم المرشح"],
    "email": ["nominee email", "nominee work email", "nominee's email", "email of nominee", "candidate email", "champion email", "بريد المرشح"],
    "entity": ["entity", "organisation", "organization", "ministry", "authority", "الجهة"],
    "department": ["department", "directorate", "division", "unit", "الإدارة"],
    "platform": ["platform", "system", "المنصة"],
    "workflow": ["workflow", "process", "business process", "الإجراء"],
    "route": ["nomination type", "nomination route", "who is nominating", "self or", "route"],
    "nominator_name": ["your name", "nominator name", "nominated by", "name"],
    "nominator_email": ["your email", "nominator email", "email"],
    "reason": ["reason", "why", "justification", "السبب"],
    "manager_name": ["manager name", "line manager name", "line manager", "manager"],
    "manager_email": ["manager email", "line manager email", "manager's email"],
    "consent": ["consent", "agree", "agreed", "permission", "الموافقة"],
}
# Specific fields first so generic hints ("name", "email", "manager") don't steal their columns.
MATCH_ORDER = ["name", "email", "entity", "department", "platform", "workflow", "route", "reason",
               "manager_email", "manager_name", "consent", "nominator_email", "nominator_name"]
YES = {"yes", "y", "true", "1", "agree", "agreed", "i agree", "consented", "نعم", "موافق"}


class ImportErrorMsg(Exception):
    pass


def read_table(filename: str, data: bytes) -> tuple[list[str], list[list[str]]]:
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb.worksheets[0]
            rows = [["" if v is None else str(v).strip() for v in r] for r in ws.iter_rows(values_only=True)]
        except Exception as e:
            raise ImportErrorMsg(f"The Excel file could not be read ({type(e).__name__}). Save it again as .xlsx or .csv.")
    elif ext == ".csv":
        text = None
        for enc in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ImportErrorMsg("The CSV file's text encoding could not be read. Save it as 'CSV UTF-8'.")
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t") if text.strip() else csv.excel
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    else:
        raise ImportErrorMsg("Please upload the survey results as an Excel (.xlsx) or CSV file.")
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        raise ImportErrorMsg("The file has no data rows under the header row.")
    header = rows[0]
    width = len(header)
    body = [(r + [""] * width)[:width] for r in rows[1:]]
    return header, body


def guess_mapping(header: list[str], saved: dict[str, str] | None = None) -> dict[str, str]:
    """Return {field_key: column_header}. A saved mapping wins where its columns still exist."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    if saved:
        for k, col in saved.items():
            if col in header and k in FIELD_KEYS:
                mapping[k] = col
                used.add(col)
    norm = {h: re.sub(r"\s+", " ", h.lower()).strip() for h in header}
    for key in MATCH_ORDER:
        if key in mapping:
            continue
        for hint in HINTS[key]:
            match = next((h for h in header if h not in used and (norm[h] == hint or hint in norm[h])), None)
            if match:
                mapping[key] = match
                used.add(match)
                break
    return mapping


def normalise_route(value: str) -> str:
    v = (value or "").lower()
    if "self" in v or "myself" in v or "ذات" in v:
        return "self"
    if "manager" in v or "مدير" in v:
        return "manager"
    if v:
        return "peer"
    return ""


def apply_mapping(header: list[str], rows: list[list[str]], mapping: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Convert rows into nominee dicts. Returns (records, row_problems)."""
    idx = {k: header.index(col) for k, col in mapping.items() if col in header}
    missing = [label for key, label, req in FIELDS if req and key not in idx]
    if missing:
        raise ImportErrorMsg("Match a column for: " + ", ".join(missing) + ".")
    records, problems = [], []
    for n, row in enumerate(rows, start=2):
        rec = {k: row[i].strip() for k, i in idx.items()}
        rec["source_row"] = dict(zip(header, row))
        rec["row_number"] = n
        if not rec.get("name"):
            problems.append(f"Row {n}: no nominee name, skipped.")
            continue
        if not rec.get("entity"):
            problems.append(f"Row {n}: no entity for {rec['name']}, skipped.")
            continue
        rec["email"] = (rec.get("email") or "").lower()
        if rec["email"] and "@" not in rec["email"]:
            problems.append(f"Row {n}: '{rec['email']}' is not an email address; imported without email.")
            rec["email"] = ""
        rec["route"] = normalise_route(rec.get("route", ""))
        rec["consent"] = (rec.get("consent") or "").strip().lower() in YES
        records.append(rec)
    return records, problems
