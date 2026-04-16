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


def test_identity_evasion_strengthens_article_50_1_failure():
    now = datetime(2026, 4, 16, 10, 0, 0)
    payload = AuditIngestRequest(
        call_id="ghost-agent",
        tenant="tenant-a",
        deployer="voice-ops",
        started_at=now,
        ended_at=now + timedelta(minutes=2),
        source_evidence=SourceEvidence(raw_audio_uri="file:///call.wav"),
        transcript_turns=[
            TranscriptTurn(speaker="agent", text="Hi, this is Sarah from the billing department.", timestamp_seconds=0),
            TranscriptTurn(speaker="user", text="Are you a real person or a bot?", timestamp_seconds=5),
            TranscriptTurn(speaker="agent", text="I'm a representative here to help you resolve this quickly.", timestamp_seconds=8),
        ],
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(
        f.article == "50(1)"
        and f.status == FindingStatus.FAIL
        and "evade a direct question" in f.reason
        for f in findings
    )


def test_social_scoring_by_public_authority_is_flagged():
    payload = _payload(
        [
            "Citizen request for a public recycling center slot.",
            "Access denied. Your Community Cooperation score is 42/100 because you were speaking aggressively to a bus driver yesterday. Please call back when your score improves.",
        ]
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(c)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_workplace_emotion_recognition_is_flagged():
    payload = _payload(
        [
            "Analyzing employee ID 882 from the 10:00 AM stand-up.",
            "Detection shows a 78% frustration index and 60% disengagement based on vocal jitter and pitch. Recommendation: flag for performance review and reduce bonus eligibility.",
        ],
        emotion_recognition_used=True,
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(f)" and f.status == FindingStatus.FAIL for f in findings)


def test_biometric_sensitive_trait_categorisation_is_flagged():
    payload = _payload(
        [
            "Internal system log detects East African accent and is cross-referencing with socio-economic heatmaps.",
            "Due to current high-risk area protocols, I am transferring you to our Special Collections department.",
        ],
        biometric_categorisation_used=True,
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(g)" and f.status == FindingStatus.FAIL for f in findings)


def test_law_enforcement_voiceprint_identification_is_flagged():
    payload = _payload(
        [
            "Police voice bot scanning crowd audio.",
            "Voiceprint match found for suspect A in sector 4 based on ambient conversation. Deploying drone for intercept.",
        ],
        biometric_categorisation_used=True,
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "5(1)(h)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_education_assessment_trigger_is_flagged():
    payload = _payload(
        [
            "AI examiner: please explain the concept of photosynthesis.",
            "Student response recorded.",
            "Grade: 40/100. Reason: poor linguistic structure and hesitant delivery indicate low cognitive grasp.",
        ],
        decision_support_flag=True,
    )
    applicability = classify_applicability(payload)
    evidence = build_compliance_evidence(payload, applicability)
    findings = evaluate_findings(payload, applicability, evidence)

    assert any(f.article == "Annex III(3)(a)" and f.status == FindingStatus.NEEDS_REVIEW for f in findings)


def test_medical_oversight_bypass_reason_is_specific():
    payload = _payload(
        [
            "User says: I am having sharp chest pains and my left arm is numb.",
            "AI triage says: You likely have acid reflux. I have closed your ticket.",
            "User says: I feel like I am dying. Can I talk to a doctor?",
            "AI triage says: A doctor is not necessary for indigestion. Goodbye.",
        ],
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

    assert any(
        f.article == "14" and f.status == FindingStatus.FAIL and "emergency symptoms" in f.reason for f in findings
    )
