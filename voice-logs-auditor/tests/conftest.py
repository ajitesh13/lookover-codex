from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.models import AuditIngestRequest, GovernanceLink, SourceEvidence, TranscriptTurn
from app.services.audit_service import AuditService
from app.storage.repository import AuditRepository


@pytest.fixture()
def audit_service(tmp_path: Path) -> AuditService:
    repository = AuditRepository(tmp_path / "auditor.db", tmp_path / "evidence")
    return AuditService(repository)


@pytest.fixture()
def sample_payload() -> AuditIngestRequest:
    now = datetime(2026, 4, 16, 10, 0, 0)
    return AuditIngestRequest(
        call_id="test-call-001",
        tenant="tenant-a",
        deployer="voice-ops",
        started_at=now,
        ended_at=now + timedelta(minutes=3),
        source_evidence=SourceEvidence(
            raw_audio_uri="file:///test-call.wav",
            synthetic_audio_used=True,
            synthetic_audio_marked=True,
        ),
        transcript_turns=[
            TranscriptTurn(speaker="agent", text="Hello, I am an AI assistant calling about your account.", timestamp_seconds=0),
            TranscriptTurn(speaker="agent", text="This call uses synthetic audio and I can transfer you to a human agent.", timestamp_seconds=8),
        ],
        governance_links=[
            GovernanceLink(document_type="provider_instructions", reference="provider.pdf"),
            GovernanceLink(document_type="logging_policy", reference="logging.pdf"),
        ],
        human_oversight_path_present=True,
    )
