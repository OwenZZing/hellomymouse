import unittest
from unittest.mock import patch
from pathlib import Path
import sys

import gspread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sheets


class FakeWorksheet:
    def __init__(self, title: str, rows=None):
        self.title = title
        self.rows = rows or []

    def row_values(self, index: int):
        if index <= len(self.rows):
            return self.rows[index - 1]
        return []

    def append_row(self, row):
        self.rows.append(list(row))


class FakeSpreadsheet:
    def __init__(self):
        self.tabs = {}

    def worksheet(self, title: str):
        if title not in self.tabs:
            raise gspread.WorksheetNotFound(title)
        return self.tabs[title]

    def add_worksheet(self, title: str, rows: int, cols: int):
        ws = FakeWorksheet(title)
        self.tabs[title] = ws
        return ws


class FakeClient:
    def __init__(self, spreadsheet: FakeSpreadsheet):
        self.spreadsheet = spreadsheet

    def open_by_key(self, key: str):
        return self.spreadsheet


class SheetsTests(unittest.TestCase):
    def test_missing_failures_sheet_is_created_with_header(self):
        spreadsheet = FakeSpreadsheet()
        client = FakeClient(spreadsheet)

        with patch.object(sheets, "_client", return_value=client):
            ws = sheets._sheet("Failures")

        self.assertEqual(ws.title, "Failures")
        self.assertEqual(ws.row_values(1), sheets._FAILURE_HEADERS)

    def test_existing_sheet_without_header_gets_header(self):
        spreadsheet = FakeSpreadsheet()
        spreadsheet.tabs["Reviews"] = FakeWorksheet("Reviews")
        client = FakeClient(spreadsheet)

        with patch.object(sheets, "_client", return_value=client):
            ws = sheets._sheet("Reviews")

        self.assertEqual(ws.row_values(1), sheets._REVIEW_HEADERS)


if __name__ == "__main__":
    unittest.main()
