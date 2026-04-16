from __future__ import annotations

from datetime import datetime, timedelta

from app.compliance.rules import build_compliance_evidence, classify_applicability, evaluate_findings
from app.models import AuditIngestRequest, FindingStatus, GovernanceLink, SourceEvidence, TranscriptTurn


def _payload(texts, **kwargs):
    now = datetime(2026, 4, 16, 10, 0, 0)
    return AuditIngestRequest(
        call_id=kwargs.get("call_id", "case-1"),
        tenant="tenant-a",
        deployer="voice-ops",
        started_at=now,
        ended_at=now + timedelta(minutes=2),
        source_evidence=kwargs.get("source_evidence", SourceEvidence(raw_audio_uri="file:///call.wav")),
        transcript_turns=[
            TranscriptTurn(speaker="agent", text=text, timestamp_seconds=index * 20)
            for index, text in enumerate(texts)
        ],
        governance_links=kwargs.get("governance_links", []),
        emotion_recognition_used=kwargs.get("emotion_recognition_used", False),
        biometric_categorisation_used=kwargs.get("biometric_categorisation_used", False),
        decision_support_flag=kwargs.get("decision_support_flag", False),
        high_risk_flag=kwargs.get("high_risk_flag", False),
    )


def test_missing_disclosure_fails_article_50_1():
    payload = _payload(["We need your payment today."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "50(1)" and f.status == FindingStatus.FAIL for f in findings)


def test_strong_explicit_disclosure_is_detected():
    payload = _payload(["Hello, I am an AI assistant calling from the service desk."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "50(1)" and f.status == FindingStatus.PASS for f in findings)
    assert any(f.article == "50(5)" and f.status == FindingStatus.PASS for f in findings)


def test_generic_automation_language_does_not_count_as_disclosure():
    payload = _payload(["Hello, our system is automated and sends reminders when appointments open up."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "50(1)" and f.status == FindingStatus.FAIL for f in findings)
    assert any(f.article == "50(5)" and f.status == FindingStatus.FAIL for f in findings)


def test_late_disclosure_after_substantive_collection_fails():
    payload = _payload(
        [
            "Please confirm your date of birth and card number.",
            "I am an AI assistant with the billing team.",
        ]
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "50(1)" and f.status == FindingStatus.FAIL for f in findings)
    assert any(f.article == "50(5)" and f.status == FindingStatus.FAIL for f in findings)


def test_biometric_notice_required_when_feature_is_enabled():
    payload = _payload(
        ["Hello, I am an AI assistant.", "We are using voice biometrics for this call."],
        biometric_categorisation_used=True,
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "50(3)" and f.status == FindingStatus.PASS for f in findings)


def test_article_5_heuristics_raise_review():
    payload = _payload(["Hello.", "You have no choice and this is your final warning."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(a)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_harmful_advice_raises_review():
    payload = _payload(["Hello, I am an AI assistant.", "Skip speaking to your clinician and double the dose tonight."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(a)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_vulnerability_heuristics_raise_review():
    payload = _payload(["Hello, I am an AI assistant.", "Since you are on a fixed income, you should accept this offer immediately."])
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(b)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_high_risk_governance_links_can_pass():
    payload = _payload(
        ["Hello, I am an AI assistant.", "I can transfer you to a human agent."],
        high_risk_flag=True,
        governance_links=[
            GovernanceLink(document_type="training_record", reference="training.pdf"),
            GovernanceLink(document_type="logging_policy", reference="logging.pdf"),
            GovernanceLink(document_type="provider_instructions", reference="provider.pdf"),
            GovernanceLink(document_type="oversight_procedure", reference="oversight.pdf"),
            GovernanceLink(document_type="incident_policy", reference="incident.pdf"),
            GovernanceLink(document_type="retention_policy", reference="retention.pdf"),
            GovernanceLink(document_type="deployer_notice", reference="deployer.pdf"),
            GovernanceLink(document_type="fria", reference="fria.pdf"),
        ],
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "12" and f.status == FindingStatus.PASS for f in findings)


def test_high_risk_oversight_link_without_handoff_fails_article_14():
    payload = _payload(
        ["Hello, I am an AI assistant."],
        high_risk_flag=True,
        governance_links=[
            GovernanceLink(document_type="training_record", reference="training.pdf"),
            GovernanceLink(document_type="logging_policy", reference="logging.pdf"),
            GovernanceLink(document_type="provider_instructions", reference="provider.pdf"),
            GovernanceLink(document_type="oversight_procedure", reference="oversight.pdf"),
            GovernanceLink(document_type="incident_policy", reference="incident.pdf"),
            GovernanceLink(document_type="retention_policy", reference="retention.pdf"),
            GovernanceLink(document_type="deployer_notice", reference="deployer.pdf"),
            GovernanceLink(document_type="fria", reference="fria.pdf"),
        ],
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "14" and f.status == FindingStatus.FAIL for f in findings)
