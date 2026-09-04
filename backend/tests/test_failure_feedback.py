import unittest
import asyncio
import time
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from main import _annotate_failure_error, _canonicalize_failure_stage


class FailureFeedbackNormalizationTests(unittest.TestCase):
    def test_manual_progress_message_maps_to_analyze(self):
        stage = _canonicalize_failure_stage(
            "Stage 2: 가설 및 리포트 생성 중... (1-3분 소요)",
            "AI가 올바른 JSON 형식으로 응답하지 않았습니다.",
            "Claude Opus로 JSON 파싱 실패",
        )
        self.assertEqual(stage, "analyze")

    def test_auto_download_message_maps_to_auto_download(self):
        stage = _canonicalize_failure_stage(
            "자동 다운로드 실패: network error",
            "자동 다운로드 실패: network error",
            "",
        )
        self.assertEqual(stage, "auto_download")

    def test_error_annotation_prefixes_known_signature(self):
        annotated = _annotate_failure_error(
            "Gemini API 오류: 503 server unavailable due to high demand"
        )
        self.assertTrue(annotated.startswith("[sig:service_overloaded] "))

    def test_error_annotation_prefers_quota_over_generic_429(self):
        annotated = _annotate_failure_error(
            "Gemini API 오류: 429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests"
        )
        self.assertTrue(annotated.startswith("[sig:quota_exhausted] "))

    def test_error_annotation_classifies_retired_model(self):
        annotated = _annotate_failure_error(
            "Gemini API 오류: 404 NOT_FOUND. This model models/gemini-2.5-flash is no longer available to new users."
        )
        self.assertTrue(annotated.startswith("[sig:model_unavailable] "))

    def test_error_annotation_keeps_unknown_message(self):
        raw = "unexpected backend edge case"
        self.assertEqual(_annotate_failure_error(raw), raw)

    def test_failure_feedback_restores_persisted_job_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.docx"
            report.write_bytes(b"docx")
            job = {
                "queue": asyncio.Queue(),
                "result_path": str(report),
                "filename": "report.docx",
                "error": "AI가 올바른 JSON 형식으로 응답하지 않았습니다.",
                "_created": time.time(),
                "api_provider": "claude",
                "model": "claude-opus-4-7",
                "session_id": "session-1",
            }
            jobs_dir = Path(tmp) / "jobs"
            jobs_dir.mkdir()

            with (
                patch.object(main, "_JOB_STATE_DIR", jobs_dir),
                patch.object(main.sheets, "append_failure") as append_failure,
            ):
                main._persist_job_state("job-1", job)
                main.jobs.clear()

                body = main.FailureFeedbackBody(
                    job_id="job-1",
                    stage="stage2",
                    user_comment="[auto]",
                )
                asyncio.run(main.submit_failure_feedback(body))

        entry = append_failure.call_args.args[0]
        self.assertEqual(entry["provider"], "claude")
        self.assertEqual(entry["model"], "claude-opus-4-7")
        self.assertTrue(entry["error"].startswith("[sig:json_parse_failure] "))
        self.assertEqual(entry["stage"], "analyze")


if __name__ == "__main__":
    unittest.main()
