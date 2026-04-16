from __future__ import annotations

from app.compliance.rules import (
    build_compliance_evidence,
    build_event_timeline,
    classify_applicability,
    evaluate_findings,
    overall_disposition,
    payload_hash,
)
from app.models import (
    AccessAuditEvent,
    AuditIngestRequest,
    EvidenceBundle,
    IntegrityPrivacy,
    LegalHoldRequest,
    RetrievalQuery,
    VoiceAuditRecord,
)
from app.storage.repository import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def ingest_audit(self, payload: AuditIngestRequest) -> VoiceAuditRecord:
        applicability = classify_applicability(payload)
        evidence = build_compliance_evidence(payload, applicability)
        findings = evaluate_findings(payload, applicability, evidence)
        event_timeline = build_event_timeline(payload, evidence)
        version = self.repository.next_version(payload.tenant, payload.call_id)
        record = VoiceAuditRecord(
            call_id=payload.call_id,
            tenant=payload.tenant,
            deployer=payload.deployer,
            customer_reference=payload.customer_reference,
            jurisdiction=payload.jurisdiction,
            language=payload.language,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            channel=payload.channel,
            agent_version=payload.agent_version,
            policy_version=payload.policy_version,
            source_evidence=payload.source_evidence,
            transcript_turns=payload.transcript_turns,
            event_timeline=event_timeline,
            governance_links=payload.governance_links,
            compliance_evidence=evidence,
            integrity_privacy=IntegrityPrivacy(
                content_hash=payload_hash(payload),
                storage_region=payload.storage_region,
                encryption_key_reference=payload.encryption_key_reference,
                access_classification=payload.access_classification,
                retention_expiry=payload.retention_expiry,
            ),
            applicability=applicability,
            findings=findings,
            disposition=overall_disposition(findings),
            version=version,
        )
        return self.repository.save_audit(record)

    def get_audit(self, tenant: str, call_id: str) -> VoiceAuditRecord | None:
        record = self.repository.get_latest_audit(tenant, call_id)
        if record:
            self.repository.log_access(tenant, call_id, record.version, AccessAuditEvent(action="record_viewed"))
        return record

    def list_audits(self) -> list[VoiceAuditRecord]:
        return self.repository.list_audits()

    def list_findings(self, query: RetrievalQuery) -> list[dict[str, object]]:
        return self.repository.query_findings(query)

    def get_bundle(self, tenant: str, call_id: str) -> EvidenceBundle | None:
        return self.repository.get_bundle(tenant, call_id)

    def get_access_history(self, tenant: str, call_id: str) -> list[AccessAuditEvent]:
        current = self.repository.get_latest_audit(tenant, call_id)
        if not current:
            return []
        return self.repository.get_access_events(tenant, call_id, current.version)

    def reanalyse(self, tenant: str, call_id: str) -> VoiceAuditRecord | None:
        current = self.repository.get_latest_audit(tenant, call_id)
        if not current:
            return None
        payload = AuditIngestRequest(
            call_id=current.call_id,
            tenant=current.tenant,
            deployer=current.deployer,
            customer_reference=current.customer_reference,
            jurisdiction=current.jurisdiction,
            language=current.language,
            started_at=current.started_at,
            ended_at=current.ended_at,
            channel=current.channel,
            agent_version=current.agent_version,
            policy_version=current.policy_version,
            source_evidence=current.source_evidence,
            transcript_turns=current.transcript_turns,
            governance_links=current.governance_links,
            emotion_recognition_used=current.compliance_evidence.emotion_recognition_used,
            biometric_categorisation_used=current.compliance_evidence.biometric_categorisation_used,
            decision_support_flag=current.compliance_evidence.decision_support_flag,
            human_oversight_path_present=current.compliance_evidence.human_oversight_path_present,
            notice_to_affected_person_present=current.compliance_evidence.notice_to_affected_person_present,
            high_risk_flag=current.compliance_evidence.high_risk_flag,
            storage_region=current.integrity_privacy.storage_region,
            encryption_key_reference=current.integrity_privacy.encryption_key_reference,
            retention_expiry=current.integrity_privacy.retention_expiry,
            access_classification=current.integrity_privacy.access_classification,
        )
        return self.ingest_audit(payload)

    def set_legal_hold(self, tenant: str, call_id: str, request: LegalHoldRequest) -> VoiceAuditRecord | None:
        return self.repository.set_legal_hold(tenant, call_id, request.enabled)
