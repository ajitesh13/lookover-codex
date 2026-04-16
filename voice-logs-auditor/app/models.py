from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


SAFE_AUDIT_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class InvalidAuditIdentifier(ValueError):
    pass


def validate_audit_identifier(value: str, field_name: str) -> str:
    if not SAFE_AUDIT_IDENTIFIER_RE.fullmatch(value):
        raise InvalidAuditIdentifier(
            f"{field_name} must use 1-128 safe characters: letters, numbers, dot, underscore, colon, or dash"
        )
    return value


class Applicability(str, Enum):
    TRANSPARENCY_ONLY = "transparency_only"
    TRANSPARENCY_PLUS_BIOMETRICS = "transparency_plus_biometrics"
    POTENTIAL_HIGH_RISK = "potential_high_risk"
    HIGH_RISK_CONFIRMED = "high_risk_confirmed"
    OUT_OF_SCOPE_FOR_LOG_ONLY_REVIEW = "out_of_scope_for_log_only_review"


class FindingStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUABLE_FROM_LOGS = "not_evaluable_from_logs"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceType(str, Enum):
    TRANSCRIPT = "transcript"
    METADATA = "metadata"
    GOVERNANCE = "governance"
    SYSTEM = "system"


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    timestamp_seconds: float = 0.0


class GovernanceLink(BaseModel):
    document_type: str
    reference: str
    present: bool = True
    notes: str | None = None


class SourceEvidence(BaseModel):
    raw_audio_uri: str
    transcript_uri: str | None = None
    diarization_available: bool = True
    asr_confidence: float | None = None
    model_provider: str | None = None
    model_id: str | None = None
    policy_bundle_id: str | None = None
    synthetic_audio_used: bool = False
    synthetic_audio_marked: bool = False
    deepfake_like_content_flag: bool = False


class ComplianceEvidence(BaseModel):
    ai_disclosure_status: str = "unknown"
    disclosure_timestamp: float | None = None
    synthetic_audio_used: bool = False
    deepfake_like_content_flag: bool = False
    emotion_recognition_used: bool = False
    biometric_categorisation_used: bool = False
    decision_support_flag: bool = False
    human_oversight_path_present: bool = False
    notice_to_affected_person_present: bool = False
    high_risk_flag: bool = False
    article_applicability: list[str] = Field(default_factory=list)


class IntegrityPrivacy(BaseModel):
    content_hash: str
    redaction_version: int = 1
    legal_hold: bool = False
    storage_region: str = "eu-west-1"
    encryption_key_reference: str | None = None
    access_classification: str = "restricted"
    retention_expiry: str | None = None


class AccessAuditEvent(BaseModel):
    action: str
    actor: str = "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: str | None = None


class ComplianceFinding(BaseModel):
    article: str
    status: FindingStatus
    severity: Severity
    reason: str
    evidence_span: str
    evidence_type: EvidenceType
    confidence: float = 1.0
    manual_review_required: bool = False
    linked_external_evidence_required: bool = False
    owner: str = "compliance-team"
    remediation_due_at: str | None = None


class VoiceAuditRecord(BaseModel):
    call_id: str
    tenant: str
    deployer: str
    customer_reference: str | None = None
    jurisdiction: str = "EU"
    language: str = "en"
    started_at: datetime
    ended_at: datetime
    channel: str = "voice"
    agent_version: str
    policy_version: str
    source_evidence: SourceEvidence
    transcript_turns: list[TranscriptTurn]
    event_timeline: list[dict[str, Any]] = Field(default_factory=list)
    governance_links: list[GovernanceLink] = Field(default_factory=list)
    compliance_evidence: ComplianceEvidence
    integrity_privacy: IntegrityPrivacy
    applicability: Applicability
    findings: list[ComplianceFinding] = Field(default_factory=list)
    disposition: str = "pending"
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditIngestRequest(BaseModel):
    call_id: str
    tenant: str
    deployer: str
    customer_reference: str | None = None
    jurisdiction: str = "EU"
    language: str = "en"
    started_at: datetime
    ended_at: datetime
    channel: str = "voice"
    agent_version: str = "v1"
    policy_version: str = "policy-1"
    source_evidence: SourceEvidence
    transcript_turns: list[TranscriptTurn]
    governance_links: list[GovernanceLink] = Field(default_factory=list)
    emotion_recognition_used: bool = False
    biometric_categorisation_used: bool = False
    decision_support_flag: bool = False
    human_oversight_path_present: bool = False
    notice_to_affected_person_present: bool = False
    high_risk_flag: bool = False
    storage_region: str = "eu-west-1"
    encryption_key_reference: str | None = None
    retention_expiry: str | None = None
    access_classification: str = "restricted"
    reviewer_owner: str = "compliance-team"

    @field_validator("call_id", "tenant")
    @classmethod
    def validate_storage_identifier(cls, value: str, info: ValidationInfo) -> str:
        return validate_audit_identifier(value, info.field_name)


class LegalHoldRequest(BaseModel):
    enabled: bool


class TranscriptAuditRequest(BaseModel):
    transcript: str
    call_id: str | None = None
    tenant: str = "lookover-voice-runs"
    deployer: str = "voice-ops"
    language: str = "en"
    agent_version: str = "voice-runs-ui-v1"
    policy_version: str = "policy-voice-runs-ui"
    raw_audio_uri: str = "ui://transcript-input"
    synthetic_audio_used: bool = False
    synthetic_audio_marked: bool = False
    deepfake_like_content_flag: bool = False
    emotion_recognition_used: bool = False
    biometric_categorisation_used: bool = False
    decision_support_flag: bool = False
    human_oversight_path_present: bool = True
    notice_to_affected_person_present: bool = False
    high_risk_flag: bool = False
    governance_links: list[GovernanceLink] = Field(default_factory=list)

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("transcript must not be empty")
        return normalized


class RetrievalQuery(BaseModel):
    article: str | None = None
    status: FindingStatus | None = None
    severity: Severity | None = None
    tenant: str | None = None
    agent_version: str | None = None
    policy_version: str | None = None
    high_risk_flag: bool | None = None
    emotion_or_biometric_features: bool | None = None
    human_handoff: bool | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class EvidenceBundle(BaseModel):
    record: VoiceAuditRecord
    access_history: list[AccessAuditEvent] = Field(default_factory=list)
