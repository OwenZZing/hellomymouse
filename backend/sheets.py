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


# ── Failures (analyzer failure feedback) ─────────────────────

_FAILURE_HEADERS = [
    "created", "provider", "model", "paper_count", "stage",
    "error", "user_comment", "contact",
]


def append_failure(entry: dict):
    """Append a failure feedback entry. Auto-creates header row if missing."""
    ws = _sheet("Failures")
    if not ws.row_values(1):
        ws.append_row(_FAILURE_HEADERS)
    row = [entry.get(h, "") for h in _FAILURE_HEADERS]
    ws.append_row(row)


def get_widget() -> dict:
    from datetime import datetime, timezone
    ws = _sheet("Stairs")
    rows = ws.get_all_values()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(rows) <= 1:
        return {"stairs": 0, "button_count": 0, "last_updated": "",
                "usage_count": 0, "view_count": 0}
    # usage_count는 계속 누적 (총 사용 횟수 유지)
    max_usage = _max_col_value(rows, 3)
    last = rows[-1]
    last_date = last[0]
    # button_count, view_count: 오늘 row가 있으면 오늘 값, 없으면 0 (하루 단위 리셋)
    if last_date == today:
        today_button = int(last[2]) if len(last) > 2 and last[2] else 0
        today_views = int(last[4]) if len(last) > 4 and last[4] else 0
    else:
        today_button = 0
        today_views = 0
    return {
        "stairs": int(last[1]) if last[1] else 0,
        "button_count": today_button,
        "last_updated": last_date,
        "usage_count": max_usage,
        "view_count": today_views,
    }
