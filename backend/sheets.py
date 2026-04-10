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

_REVIEW_HEADERS = ["name", "field", "position", "stars", "comment", "provider", "model", "created"]


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


def delete_review(row_index: int):
    """Delete a review row (1-based, header=1 so first data row=2)."""
    ws = _sheet("Reviews")
    ws.delete_rows(row_index)


# ── Widget (Stairs) ──────────────────────────────────────────

_WIDGET_HEADERS = ["date", "stairs", "button_count", "usage_count", "view_count"]


def save_widget(date: str, stairs: int, button_count: int,
                usage_count: int = 0, view_count: int = 0):
    ws = _sheet("Stairs")
    if not ws.row_values(1):
        ws.append_row(_WIDGET_HEADERS)
    # Update existing row for today or append new
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if row[0] == date:
            ws.update_cell(i, 2, stairs)
            ws.update_cell(i, 3, button_count)
            ws.update_cell(i, 4, usage_count)
            ws.update_cell(i, 5, view_count)
            return
    ws.append_row([date, stairs, button_count, usage_count, view_count])


def _max_col_value(rows: list[list[str]], col_index: int) -> int:
    """Return the max int value found in col_index (0-based) across data rows."""
    best = 0
    for r in rows[1:]:
        if len(r) > col_index and r[col_index]:
            try:
                best = max(best, int(r[col_index]))
            except ValueError:
                pass
    return best


def get_widget() -> dict:
    ws = _sheet("Stairs")
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return {"stairs": 0, "button_count": 0, "last_updated": "",
                "usage_count": 0, "view_count": 0}
    # usage_count / view_count are cumulative — scan all rows so pre-migration
    # rows (missing the new columns) don't reset the totals.
    max_usage = _max_col_value(rows, 3)
    max_views = _max_col_value(rows, 4)
    last = rows[-1]
    return {
        "stairs": int(last[1]) if last[1] else 0,
        "button_count": int(last[2]) if len(last) > 2 and last[2] else 0,
        "last_updated": last[0],
        "usage_count": max_usage,
        "view_count": max_views,
    }
