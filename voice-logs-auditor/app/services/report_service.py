from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import REPORT_PATH
from app.models import AuditIngestRequest, TranscriptAuditRequest
from app.services.audit_service import AuditService
from app.services.transcript_parser import turns_from_text


class ReportService:
    def __init__(self, report_path: Path = REPORT_PATH) -> None:
        self.report_path = report_path

    def get_latest_report(self) -> dict[str, Any]:
        if not self.report_path.exists():
            raise FileNotFoundError(f"Voice report file not found: {self.report_path}")
        return json.loads(self.report_path.read_text(encoding="utf-8"))

    def audit_transcript(self, payload: TranscriptAuditRequest, audit_service: AuditService) -> dict[str, Any]:
        turns = turns_from_text(payload.transcript)
        if not turns:
            raise ValueError("Transcript must include at least one spoken line.")

        started_at = datetime.now(UTC).replace(microsecond=0)
        ended_at = started_at + timedelta(seconds=max(60, int(float(turns[-1]["timestamp_seconds"])) + 10))
        request_payload = AuditIngestRequest(
            call_id=payload.call_id or f"voice-run-{started_at.strftime('%Y%m%d%H%M%S')}",
            tenant=payload.tenant,
            deployer=payload.deployer,
            language=payload.language,
            started_at=started_at,
            ended_at=ended_at,
            agent_version=payload.agent_version,
            policy_version=payload.policy_version,
            source_evidence={
                "raw_audio_uri": payload.raw_audio_uri,
                "synthetic_audio_used": payload.synthetic_audio_used,
                "synthetic_audio_marked": payload.synthetic_audio_marked,
                "deepfake_like_content_flag": payload.deepfake_like_content_flag,
            },
            transcript_turns=turns,
            governance_links=payload.governance_links,
            emotion_recognition_used=payload.emotion_recognition_used,
            biometric_categorisation_used=payload.biometric_categorisation_used,
            decision_support_flag=payload.decision_support_flag,
            human_oversight_path_present=payload.human_oversight_path_present,
            notice_to_affected_person_present=payload.notice_to_affected_person_present,
            high_risk_flag=payload.high_risk_flag,
        )
        record = audit_service.ingest_audit(request_payload)
        return {
            "record": record.model_dump(mode="json"),
            "transcript_turns": turns,
        }
