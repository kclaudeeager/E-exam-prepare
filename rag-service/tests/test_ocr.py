"""Tests for the RAG service OCR handwritten endpoint.

All Groq API calls are mocked — no external calls.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Mock Groq response ────────────────────────────────────────────────────────


def _mock_groq_response(text: str = "The answer is 42."):
    """Create a mock Groq chat completion response."""
    mock_message = MagicMock()
    mock_message.content = text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestOCRHandwritten:
    @patch("app.routes.ocr.settings")
    def test_ocr_no_api_key_returns_503(self, mock_settings):
        mock_settings.GROQ_API_KEY = ""
        resp = client.post(
            "/ocr/handwritten",
            json={"image_base64": "abc123"},
        )
        assert resp.status_code == 503
        assert "GROQ_API_KEY" in resp.json()["detail"]

    @patch("app.routes.ocr.settings")
    @patch("groq.Groq")
    def test_ocr_success(self, MockGroq, mock_settings):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_VISION_MODEL = "test-model"

        mock_groq_instance = MagicMock()
        mock_groq_instance.chat.completions.create.return_value = _mock_groq_response(
            "y = mx + b"
        )
        MockGroq.return_value = mock_groq_instance

        resp = client.post(
            "/ocr/handwritten",
            json={"image_base64": "dGVzdCBpbWFnZSBkYXRh"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["text"] == "y = mx + b"

    @patch("app.routes.ocr.settings")
    @patch("groq.Groq")
    def test_ocr_with_custom_prompt(self, MockGroq, mock_settings):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_VISION_MODEL = "test-model"

        mock_groq_instance = MagicMock()
        mock_groq_instance.chat.completions.create.return_value = _mock_groq_response(
            "Kigali"
        )
        MockGroq.return_value = mock_groq_instance

        resp = client.post(
            "/ocr/handwritten",
            json={
                "image_base64": "dGVzdA==",
                "prompt": "What city name is written here?",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Kigali"

    @patch("app.routes.ocr.settings")
    @patch("groq.Groq")
    def test_ocr_with_data_uri_png(self, MockGroq, mock_settings):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_VISION_MODEL = "test-model"

        mock_groq_instance = MagicMock()
        mock_groq_instance.chat.completions.create.return_value = _mock_groq_response(
            "Hello World"
        )
        MockGroq.return_value = mock_groq_instance

        resp = client.post(
            "/ocr/handwritten",
            json={"image_base64": "data:image/png;base64,iVBORw0KGg=="},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Hello World"

        # Verify the Groq call used the right MIME type
        call_kwargs = mock_groq_instance.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        if messages:
            image_content = messages[0]["content"][1]["image_url"]["url"]
            assert image_content.startswith("data:image/png;base64,")

    @patch("app.routes.ocr.settings")
    @patch("groq.Groq")
    def test_ocr_groq_raises_error(self, MockGroq, mock_settings):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_VISION_MODEL = "test-model"

        mock_groq_instance = MagicMock()
        mock_groq_instance.chat.completions.create.side_effect = RuntimeError(
            "API down"
        )
        MockGroq.return_value = mock_groq_instance

        resp = client.post(
            "/ocr/handwritten",
            json={"image_base64": "dGVzdA=="},
        )
        assert resp.status_code == 500
        assert "OCR failed" in resp.json()["detail"]

    def test_ocr_missing_body_field(self):
        resp = client.post("/ocr/handwritten", json={})
        assert resp.status_code == 422  # Pydantic validation

    @patch("app.routes.ocr.settings")
    @patch("groq.Groq")
    def test_ocr_empty_result(self, MockGroq, mock_settings):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_VISION_MODEL = "test-model"

        mock_groq_instance = MagicMock()
        mock_groq_instance.chat.completions.create.return_value = _mock_groq_response("")
        MockGroq.return_value = mock_groq_instance

        resp = client.post(
            "/ocr/handwritten",
            json={"image_base64": "dGVzdA=="},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == ""
        assert resp.json()["success"] is True


class TestHealthCheck:
    """Quick sanity check — health endpoint should always work."""

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
