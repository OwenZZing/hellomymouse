import tempfile
import time
import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class JobStatusRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main.jobs.clear()

    def tearDown(self):
        main.jobs.clear()

    def test_running_job_returns_running_status(self):
        main.jobs["job-1"] = {
            "queue": None,
            "result_path": "",
            "filename": "",
            "error": "",
            "_created": time.time(),
            "session_id": "session-1",
        }

        res = self.client.get("/api/job/job-1/status?session=session-1")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "running"})

    def test_completed_job_returns_done_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.docx"
            report.write_bytes(b"docx")
            main.jobs["job-1"] = {
                "queue": None,
                "result_path": str(report),
                "filename": "report.docx",
                "error": "",
                "_created": time.time(),
                "session_id": "session-1",
            }

            res = self.client.get("/api/job/job-1/status?session=session-1")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "done", "filename": "report.docx"})

    def test_failed_job_returns_error_status(self):
        main.jobs["job-1"] = {
            "queue": None,
            "result_path": "",
            "filename": "",
            "error": "backend failed",
            "_created": time.time(),
            "session_id": "session-1",
        }

        res = self.client.get("/api/job/job-1/status?session=session-1")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "error", "error": "backend failed"})


if __name__ == "__main__":
    unittest.main()
