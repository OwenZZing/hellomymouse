"""Google Sheets helper for persistent reviews & widget data."""
from __future__ import annotations
import json
import os
import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SPREADSHEET_ID = "16CnsaRjxfECbpE4mnoPdpGMydpbtSDEb5NltslfBO5s"

_gc: gspread.Client | None = None


def _client() -> gspread.Client:
    global _gc
    if _gc is None:
        raw = os.environ.get("GOOGLE_CREDENTIALS", "")
        if not raw:
            raise RuntimeError("GOOGLE_CREDENTIALS env var not set")
        # Railway may insert real newlines — collapse all whitespace
        raw = " ".join(raw.split())
        creds_dict = json.loads(raw)
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        _gc = gspread.authorize(creds)
    return _gc


def _sheet(tab: str) -> gspread.Worksheet:
    spreadsheet = _client().open_by_key(_SPREADSHEET_ID)
    return spreadsheet.worksheet(tab)


# ── Reviews ──────────────────────────────────────────────────

_REVIEW_HEADERS = ["name", "field", "stars", "comment", "provider", "model", "created"]


def append_review(review: dict):
    ws = _sheet("Reviews")
    if not ws.row_values(1):
        ws.append_row(_REVIEW_HEADERS)
    row = [review.get(h, "") for h in _REVIEW_HEADERS]
    ws.append_row(row)


def get_reviews() -> list[dict]:
    ws = _sheet("Reviews")
    rows = ws.get_all_records()
    return rows


# ── Widget (Stairs) ──────────────────────────────────────────

_WIDGET_HEADERS = ["date", "stairs", "button_count"]


def save_widget(date: str, stairs: int, button_count: int):
    ws = _sheet("Stairs")
    if not ws.row_values(1):
        ws.append_row(_WIDGET_HEADERS)
    # Update existing row for today or append new
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if row[0] == date:
            ws.update_cell(i, 2, stairs)
            ws.update_cell(i, 3, button_count)
            return
    ws.append_row([date, stairs, button_count])


def get_widget() -> dict:
    ws = _sheet("Stairs")
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return {"stairs": 0, "button_count": 0, "last_updated": ""}
    last = rows[-1]
    return {
        "stairs": int(last[1]) if last[1] else 0,
        "button_count": int(last[2]) if last[2] else 0,
        "last_updated": last[0],
    }
