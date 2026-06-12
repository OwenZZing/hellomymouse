import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class StatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sessions_dir = self.root / "sessions"
        self.jobs_dir = self.root / "jobs"
        self.sessions_dir.mkdir()
        self.jobs_dir.mkdir()

    def tearDown(self):
        main.sessions.clear()
        main.jobs.clear()
        self.tmp.cleanup()

    def test_persisted_session_is_restored_after_memory_loss(self):
        workdir = self.root / "upload"
        workdir.mkdir()
        pdf = workdir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        session = {
            "lab_paths": [str(pdf)],
            "ref_paths": [],
            "tmpdir": str(workdir),
            "_created": time.time(),
        }

        with patch.object(main, "_SESSION_STATE_DIR", self.sessions_dir):
            main._persist_session_state("session-1", session)
            main.sessions.clear()
            restored = main._get_session("session-1")

        self.assertIsNotNone(restored)
        self.assertEqual(restored["lab_paths"], [str(pdf)])
        self.assertEqual(restored["tmpdir"], str(workdir))

    def test_persisted_completed_job_is_restored_after_memory_loss(self):
        report = self.root / "report.docx"
        report.write_bytes(b"docx")
        job = {
            "queue": asyncio.Queue(),
            "result_path": str(report),
            "filename": "report.docx",
            "error": "",
            "_created": time.time(),
            "api_provider": "claude",
            "model": "claude-opus-4-7",
            "session_id": "session-1",
        }

        with patch.object(main, "_JOB_STATE_DIR", self.jobs_dir):
            main._persist_job_state("job-1", job)
            main.jobs.clear()
            restored = main._get_job("job-1")

        self.assertIsNotNone(restored)
        self.assertEqual(restored["result_path"], str(report))
        self.assertEqual(restored["filename"], "report.docx")
        self.assertEqual(restored["session_id"], "session-1")

    def test_cleanup_keeps_expired_session_while_related_job_is_alive(self):
        workdir = self.root / "upload"
        workdir.mkdir()
        pdf = workdir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        main.sessions["session-1"] = {
            "lab_paths": [str(pdf)],
            "ref_paths": [],
            "tmpdir": str(workdir),
            "_created": time.time() - (main._SESSION_TTL_SECONDS + 10),
        }
        main.jobs["job-1"] = {
            "queue": asyncio.Queue(),
            "result_path": "",
            "filename": "",
            "error": "",
            "_created": time.time(),
            "api_provider": "claude",
            "model": "claude-opus-4-7",
            "session_id": "session-1",
        }

        main._cleanup_expired()

        self.assertIn("session-1", main.sessions)
        self.assertTrue(workdir.exists())

    def test_cleanup_removes_expired_result_file_with_job(self):
        report = self.root / "report.docx"
        report.write_bytes(b"docx")
        main.jobs["job-1"] = {
            "queue": asyncio.Queue(),
            "result_path": str(report),
            "filename": "report.docx",
            "error": "",
            "_created": time.time() - (main._JOB_TTL_SECONDS + 10),
            "api_provider": "claude",
            "model": "claude-opus-4-7",
            "session_id": "session-1",
        }

        main._cleanup_expired()

        self.assertNotIn("job-1", main.jobs)
        self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
