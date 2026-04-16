from __future__ import annotations

import json

from app.models import FindingStatus, LegalHoldRequest, RetrievalQuery


def test_ingest_creates_latest_record(audit_service, sample_payload):
    record = audit_service.ingest_audit(sample_payload)

    assert record.version == 1
    assert record.disposition in {"pass", "soft_fail", "needs_review", "hard_fail"}
    assert any(f.article == "50(1)" and f.status == FindingStatus.PASS for f in record.findings)


def test_reanalysis_creates_new_version(audit_service, sample_payload):
    audit_service.ingest_audit(sample_payload)
    second = audit_service.reanalyse(sample_payload.tenant, sample_payload.call_id)

    assert second is not None
    assert second.version == 2


def test_legal_hold_updates_record(audit_service, sample_payload):
    audit_service.ingest_audit(sample_payload)
    updated = audit_service.set_legal_hold(sample_payload.tenant, sample_payload.call_id, LegalHoldRequest(enabled=True))

    assert updated is not None
    assert updated.integrity_privacy.legal_hold is True


def test_versions_are_isolated_per_tenant(audit_service, sample_payload):
    audit_service.ingest_audit(sample_payload)
    second_payload = sample_payload.model_copy(update={"tenant": "tenant-b"})

    second = audit_service.ingest_audit(second_payload)
    latest_original = audit_service.get_audit(sample_payload.tenant, sample_payload.call_id)

    assert second.version == 1
    assert latest_original is not None
    assert latest_original.tenant == sample_payload.tenant
    assert latest_original.version == 1


def test_legal_hold_rewrites_all_versions_consistently(audit_service, sample_payload):
    first = audit_service.ingest_audit(sample_payload)
    second = audit_service.reanalyse(sample_payload.tenant, sample_payload.call_id)

    updated = audit_service.set_legal_hold(sample_payload.tenant, sample_payload.call_id, LegalHoldRequest(enabled=True))

    assert second is not None
    assert updated is not None
    for record in (first, second):
        evidence_path = audit_service.repository._evidence_path(record.tenant, record.call_id, record.version)
        stored_record = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert stored_record["integrity_privacy"]["legal_hold"] is True


def test_findings_filter_returns_matching_article(audit_service, sample_payload):
    audit_service.ingest_audit(sample_payload)
    findings = audit_service.list_findings(RetrievalQuery(article="50(1)", tenant="tenant-a"))

    assert findings
    assert all(item["article"] == "50(1)" for item in findings)
