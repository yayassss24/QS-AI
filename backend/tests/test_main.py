"""Tests for main.py — API endpoint behavior."""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestEndpointDetectTemplate:
    def test_requires_file(self):
        resp = client.post("/api/detect-template")
        assert resp.status_code == 422

    def test_accepts_xlsx(self, temp_xlsx):
        with open(temp_xlsx, "rb") as f:
            resp = client.post("/api/detect-template", files={"file": ("test.xlsx", f, "application/octet-stream")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "data" in data


class TestEndpointExtractFile:
    def test_rejects_unsupported_format(self):
        resp = client.post("/api/extract-file", files={"file": ("test.xyz", b"data", "application/octet-stream")})
        assert resp.status_code == 400

    def test_accepts_pdf(self):
        resp = client.post("/api/extract-file", files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")})
        assert resp.status_code == 200

    def test_accepts_image(self):
        resp = client.post("/api/extract-file", files={"file": ("test.png", b"PNG dummy", "image/png")})
        assert resp.status_code == 200


class TestEndpointExtractPdfLegacy:
    def test_backward_compat(self):
        resp = client.post("/api/extract-pdf", files={"file": ("test.pdf", b"%PDF", "application/pdf")})
        assert resp.status_code == 200


class TestEndpointChat:
    @patch("main.byok_manager", MagicMock())
    @patch("modules.chat_handler.ChatHandler.chat", return_value={"response_text": "ok", "action": {}, "flagged_items": []})
    def test_chat_with_minimal_body(self, mock_chat):
        resp = client.post("/api/chat", json={
            "user_message": "test",
            "boq_state": [],
            "template_mapping": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "data" in data


class TestEndpointByok:
    @patch("main.byok_manager", MagicMock())
    def test_validate_requires_key(self):
        resp = client.post("/api/byok/validate", json={})
        assert resp.status_code == 400

    @patch("main.byok_manager", MagicMock())
    def test_validate_with_key(self):
        resp = client.post("/api/byok/validate", json={"api_key": "test-key"})
        assert resp.status_code == 200

    @patch("main.byok_manager", MagicMock())
    def test_save_requires_user_id_and_key(self):
        resp = client.post("/api/byok/save", json={})
        assert resp.status_code == 400
