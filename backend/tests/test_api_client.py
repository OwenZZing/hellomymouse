import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.api_client import APIClient


def _blocked_response():
    return SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="SAFETY"))],
        text="",
    )


def _ok_response(text: str):
    return SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        text=text,
    )


class GeminiFallbackTests(unittest.TestCase):
    def test_gemini_safety_fallback_uses_different_model(self):
        client = APIClient.__new__(APIClient)
        client.provider = "gemini"
        client.model = "gemini-2.5-flash"
        calls = []

        def fake_generate(model, _contents, _max_tokens):
            calls.append(model)
            if len(calls) < 3:
                return _blocked_response()
            return _ok_response("ok-from-fallback")

        client._gemini_generate = fake_generate

        with patch("analyzer.api_client.time.sleep", return_value=None):
            text = client._gemini_with_retry("user", "system", 128)

        self.assertEqual(text, "ok-from-fallback")
        self.assertEqual(calls[:2], ["gemini-2.5-flash", "gemini-2.5-flash"])
        self.assertEqual(calls[2], "gemini-2.5-flash-lite")


if __name__ == "__main__":
    unittest.main()
