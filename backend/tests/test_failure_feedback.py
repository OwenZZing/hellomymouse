import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

    def test_error_annotation_keeps_unknown_message(self):
        raw = "unexpected backend edge case"
        self.assertEqual(_annotate_failure_error(raw), raw)


if __name__ == "__main__":
    unittest.main()
