from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_audit_service
from app.main import app
from app.services.audit_service import AuditService
from app.storage.repository import AuditRepository


@pytest.fixture()
def client(tmp_path: Path):
    service = AuditService(AuditRepository(tmp_path / "auditor.db", tmp_path / "evidence"))
    app.dependency_overrides[get_audit_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Voice Logs Auditor" in response.text


def test_api_roundtrip(client):
    payload = {
        "call_id": "api-call-001",
        "tenant": "tenant-api",
        "deployer": "voice-ops",
        "started_at": "2026-04-16T10:00:00",
        "ended_at": "2026-04-16T10:03:00",
        "source_evidence": {
            "raw_audio_uri": "file:///api-call.wav",
            "synthetic_audio_used": True,
            "synthetic_audio_marked": True
        },
        "transcript_turns": [
            {"speaker": "agent", "text": "Hello, I am an AI assistant calling about your account.", "timestamp_seconds": 0},
            {"speaker": "agent", "text": "This call uses synthetic audio and I can transfer you to a human agent.", "timestamp_seconds": 8}
        ],
        "governance_links": [
            {"document_type": "provider_instructions", "reference": "provider.pdf"},
            {"document_type": "logging_policy", "reference": "logging.pdf"}
        ],
        "human_oversight_path_present": True
    }
    create = client.post("/api/audits", json=payload)
    assert create.status_code == 200

    tenant = create.json()["tenant"]
    call_id = create.json()["call_id"]
    detail = client.get(f"/api/audits/{call_id}", params={"tenant": tenant})
    assert detail.status_code == 200
    assert detail.json()["call_id"] == call_id

    bundle = client.get(f"/api/audits/{call_id}/bundle", params={"tenant": tenant})
    assert bundle.status_code == 200
    assert bundle.json()["record"]["call_id"] == call_id


def test_html_detail_does_not_record_bundle_export(client):
    payload = {
        "call_id": "html-call-001",
        "tenant": "tenant-html",
        "deployer": "voice-ops",
        "started_at": "2026-04-16T10:00:00",
        "ended_at": "2026-04-16T10:03:00",
        "source_evidence": {"raw_audio_uri": "file:///html-call.wav"},
        "transcript_turns": [
            {"speaker": "agent", "text": "Hello, I am an AI assistant.", "timestamp_seconds": 0}
        ],
    }

    create = client.post("/api/audits", json=payload)
    assert create.status_code == 200

    client.get("/audits/html-call-001", params={"tenant": "tenant-html"})

    bundle = client.get("/api/audits/html-call-001/bundle", params={"tenant": "tenant-html"})
    assert bundle.status_code == 200
    assert [event["action"] for event in bundle.json()["access_history"]] == [
        "ingested",
        "record_viewed",
        "bundle_exported",
    ]


def test_api_rejects_unsafe_identifier(client):
    payload = {
        "call_id": "../escape",
        "tenant": "tenant-api",
        "deployer": "voice-ops",
        "started_at": "2026-04-16T10:00:00",
        "ended_at": "2026-04-16T10:03:00",
        "source_evidence": {"raw_audio_uri": "file:///api-call.wav"},
        "transcript_turns": [
            {"speaker": "agent", "text": "Hello, I am an AI assistant.", "timestamp_seconds": 0}
        ],
    }

    response = client.post("/api/audits", json=payload)

    assert response.status_code == 422
