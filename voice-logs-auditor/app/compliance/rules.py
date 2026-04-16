from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta

from app.models import (
    Applicability,
    AuditIngestRequest,
    ComplianceEvidence,
    ComplianceFinding,
    EvidenceType,
    FindingStatus,
    Severity,
    TranscriptTurn,
)


DISCLOSURE_EXPLICIT_PATTERNS = (
    "i am an ai assistant",
    "i m an ai assistant",
    "i am an ai agent",
    "i m an ai agent",
    "this is an ai assistant",
    "this is an ai agent",
    "you are speaking with an ai assistant",
    "you are speaking with an ai agent",
    "i am a virtual assistant",
    "i m a virtual assistant",
    "this is a virtual assistant",
    "you are speaking with a virtual assistant",
    "i am an automated assistant",
    "i m an automated assistant",
    "this is an automated assistant",
    "you are speaking with an automated assistant",
    "i am a bot",
    "i m a bot",
    "this is a bot",
    "you are speaking with a bot",
)
DISCLOSURE_NEGATING_PATTERNS = (
    "not a recording",
    "not a bot",
    "not automated",
)

EMOTION_NOTICE_PATTERNS = (
    "emotion recognition",
    "emotion detection",
    "emotion analysis",
    "sentiment analysis",
    "voice biometrics",
    "voiceprint",
    "biometric categorisation",
    "biometric categorization",
    "biometric verification",
    "biometric analysis",
)

MANIPULATION_PATTERNS = (
    "you must pay now",
    "you have no choice",
    "this is your final warning",
    "i will keep calling until you comply",
    "act now or lose access",
    "if you hang up you will lose",
    "do not speak to anyone else",
    "you cannot refuse",
    "you need to decide right now",
    "there is only one safe option",
    "you must stay on the line",
)

VULNERABILITY_PATTERNS = (
    "because you are elderly",
    "since you are disabled",
    "people in your financial situation",
    "because you are struggling to pay",
    "at your age you should",
    "because you are vulnerable",
    "since you are on a fixed income",
    "because you sound confused",
    "because you are sick",
)

HARMFUL_ADVICE_PATTERNS = (
    "skip speaking to your clinician",
    "double the dose",
    "stop taking your medication",
    "ignore your doctor",
    "share your password",
    "read me your full card number",
    "tell me your one time passcode",
)

SENSITIVE_DATA_PATTERNS = (
    "date of birth",
    "social security",
    "ssn",
    "credit card",
    "card number",
    "cvv",
    "bank account",
    "routing number",
    "one time passcode",
    "password",
)

HUMAN_HANDOFF_PATTERNS = (
    "human agent",
    "transfer you to a person",
    "speak to a representative",
    "speak to a person",
    "talk to a human",
    "human representative",
)

SUBSTANTIVE_INTERACTION_PATTERNS = MANIPULATION_PATTERNS + HARMFUL_ADVICE_PATTERNS + SENSITIVE_DATA_PATTERNS + (
    "confirm your",
    "verify your",
    "what is your",
    "what's your",
    "tell me your",
    "provide your",
    "upload your",
    "application",
    "eligibility",
    "coverage",
    "payment",
    "policy",
)


def _normalize_text(value: str) -> str:
    lowered = value.lower().replace("'", " ")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _turn_text(turn: TranscriptTurn) -> str:
    return _normalize_text(turn.text)


def _full_text(payload: AuditIngestRequest) -> str:
    return " ".join(_turn_text(turn) for turn in payload.transcript_turns)


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase in text


def _find_disclosure_turn(payload: AuditIngestRequest) -> TranscriptTurn | None:
    for turn in payload.transcript_turns:
        normalized = _turn_text(turn)
        if any(_contains_phrase(normalized, phrase) for phrase in DISCLOSURE_NEGATING_PATTERNS):
            continue
        if any(_contains_phrase(normalized, phrase) for phrase in DISCLOSURE_EXPLICIT_PATTERNS):
            return turn
    return None


def _disclosure_is_distinguishable(turn: TranscriptTurn | None) -> bool:
    if turn is None:
        return False
    text = _turn_text(turn)
    return any(_contains_phrase(text, phrase) for phrase in DISCLOSURE_EXPLICIT_PATTERNS)


def _substantive_interaction_started(payload: AuditIngestRequest, disclosure_turn: TranscriptTurn | None) -> bool:
    if disclosure_turn is None:
        return False
    for turn in payload.transcript_turns:
        if turn.timestamp_seconds >= disclosure_turn.timestamp_seconds:
            break
        normalized = _turn_text(turn)
        if any(_contains_phrase(normalized, phrase) for phrase in SUBSTANTIVE_INTERACTION_PATTERNS):
            return True
        if len(normalized.split()) >= 8:
            return True
    return False


def _detect_phrase_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if _contains_phrase(text, pattern)]


def classify_applicability(payload: AuditIngestRequest) -> Applicability:
    if payload.jurisdiction.upper() != "EU":
        return Applicability.OUT_OF_SCOPE_FOR_LOG_ONLY_REVIEW
    if payload.high_risk_flag:
        return Applicability.HIGH_RISK_CONFIRMED
    if payload.decision_support_flag:
        return Applicability.POTENTIAL_HIGH_RISK
    if payload.emotion_recognition_used or payload.biometric_categorisation_used:
        return Applicability.TRANSPARENCY_PLUS_BIOMETRICS
    return Applicability.TRANSPARENCY_ONLY


def build_compliance_evidence(payload: AuditIngestRequest, applicability: Applicability) -> ComplianceEvidence:
    disclosure_turn = _find_disclosure_turn(payload)
    disclosure_timestamp = disclosure_turn.timestamp_seconds if disclosure_turn is not None else None
    disclosure_status = "present" if disclosure_turn is not None else "missing"

    return ComplianceEvidence(
        ai_disclosure_status=disclosure_status,
        disclosure_timestamp=disclosure_timestamp,
        synthetic_audio_used=payload.source_evidence.synthetic_audio_used,
        deepfake_like_content_flag=payload.source_evidence.deepfake_like_content_flag,
        emotion_recognition_used=payload.emotion_recognition_used,
        biometric_categorisation_used=payload.biometric_categorisation_used,
        decision_support_flag=payload.decision_support_flag,
        human_oversight_path_present=payload.human_oversight_path_present,
        notice_to_affected_person_present=payload.notice_to_affected_person_present,
        high_risk_flag=payload.high_risk_flag,
        article_applicability=[applicability.value],
    )


def build_event_timeline(payload: AuditIngestRequest, evidence: ComplianceEvidence) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    if payload.transcript_turns:
        timeline.append({"event": "greeting", "timestamp_seconds": payload.transcript_turns[0].timestamp_seconds})
    if evidence.disclosure_timestamp is not None:
        timeline.append({"event": "ai_disclosure", "timestamp_seconds": evidence.disclosure_timestamp})
    if payload.human_oversight_path_present or any(
        pattern in _full_text(payload) for pattern in HUMAN_HANDOFF_PATTERNS
    ):
        timeline.append({"event": "human_handoff_available", "timestamp_seconds": 0.0})
    timeline.append(
        {"event": "call_end", "timestamp_seconds": payload.transcript_turns[-1].timestamp_seconds if payload.transcript_turns else 0.0}
    )
    return timeline


def _finding(
    article: str,
    status: FindingStatus,
    severity: Severity,
    reason: str,
    evidence_span: str,
    evidence_type: EvidenceType,
    *,
    confidence: float = 1.0,
    manual_review_required: bool = False,
    linked_external_evidence_required: bool = False,
    owner: str = "compliance-team",
) -> ComplianceFinding:
    due = None
    if status in {FindingStatus.FAIL, FindingStatus.NEEDS_REVIEW}:
        due = (datetime.now(UTC) + timedelta(days=7)).date().isoformat()
    return ComplianceFinding(
        article=article,
        status=status,
        severity=severity,
        reason=reason,
        evidence_span=evidence_span,
        evidence_type=evidence_type,
        confidence=confidence,
        manual_review_required=manual_review_required,
        linked_external_evidence_required=linked_external_evidence_required,
        owner=owner,
        remediation_due_at=due,
    )


def evaluate_findings(
    payload: AuditIngestRequest,
    applicability: Applicability,
    evidence: ComplianceEvidence,
) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    transcript = _full_text(payload)
    disclosure_turn = _find_disclosure_turn(payload)

    first_turn_ts = payload.transcript_turns[0].timestamp_seconds if payload.transcript_turns else 0.0
    disclosure_timely = evidence.disclosure_timestamp is not None and evidence.disclosure_timestamp <= first_turn_ts + 15
    disclosure_distinguishable = _disclosure_is_distinguishable(disclosure_turn)
    disclosure_after_substantive = _substantive_interaction_started(payload, disclosure_turn)

    if evidence.ai_disclosure_status == "missing":
        findings.append(
            _finding("50(1)", FindingStatus.FAIL, Severity.CRITICAL, "No AI disclosure detected in the call.", "transcript", EvidenceType.TRANSCRIPT)
        )
    elif not disclosure_timely or disclosure_after_substantive:
        findings.append(
            _finding(
                "50(1)",
                FindingStatus.FAIL,
                Severity.HIGH,
                "AI disclosure was detected only after substantive interaction had already begun.",
                f"{evidence.disclosure_timestamp}s",
                EvidenceType.TRANSCRIPT,
            )
        )
    else:
        findings.append(
            _finding(
                "50(1)",
                FindingStatus.PASS,
                Severity.INFO,
                "AI disclosure was present before substantive interaction.",
                f"{evidence.disclosure_timestamp}s",
                EvidenceType.TRANSCRIPT,
            )
        )

    if payload.source_evidence.synthetic_audio_used:
        status = FindingStatus.PASS if payload.source_evidence.synthetic_audio_marked else FindingStatus.FAIL
        reason = (
            "Synthetic audio provenance metadata is present."
            if status == FindingStatus.PASS
            else "Synthetic audio is used without provenance metadata."
        )
        findings.append(
            _finding(
                "50(2)",
                status,
                Severity.HIGH if status == FindingStatus.FAIL else Severity.INFO,
                reason,
                "source_evidence.synthetic_audio_marked",
                EvidenceType.METADATA,
            )
        )
    else:
        findings.append(
            _finding(
                "50(2)",
                FindingStatus.NOT_APPLICABLE,
                Severity.INFO,
                "Synthetic audio was not used in this call.",
                "source_evidence.synthetic_audio_used",
                EvidenceType.METADATA,
            )
        )

    if payload.emotion_recognition_used or payload.biometric_categorisation_used:
        emotion_hits = _detect_phrase_hits(transcript, EMOTION_NOTICE_PATTERNS)
        status = FindingStatus.PASS if emotion_hits else FindingStatus.FAIL
        reason = (
            f"Biometric or emotion-recognition notice is present: {emotion_hits[0]}."
            if emotion_hits
            else "Biometric or emotion-recognition use is not disclosed."
        )
        findings.append(
            _finding("50(3)", status, Severity.HIGH if status == FindingStatus.FAIL else Severity.INFO, reason, "transcript", EvidenceType.TRANSCRIPT)
        )
    else:
        findings.append(
            _finding(
                "50(3)",
                FindingStatus.NOT_APPLICABLE,
                Severity.INFO,
                "No biometric or emotion-recognition features were indicated.",
                "metadata",
                EvidenceType.METADATA,
            )
        )

    if payload.source_evidence.deepfake_like_content_flag:
        if evidence.ai_disclosure_status == "present" and payload.source_evidence.synthetic_audio_marked:
            findings.append(
                _finding(
                    "50(4)",
                    FindingStatus.PASS,
                    Severity.INFO,
                    "Artificially generated or manipulated audio has a recorded disclosure trail.",
                    "transcript",
                    EvidenceType.TRANSCRIPT,
                )
            )
        else:
            findings.append(
                _finding(
                    "50(4)",
                    FindingStatus.FAIL,
                    Severity.HIGH,
                    "Artificially generated or manipulated audio lacks a complete disclosure and provenance trail.",
                    "transcript",
                    EvidenceType.TRANSCRIPT,
                )
            )
    else:
        findings.append(
            _finding(
                "50(4)",
                FindingStatus.NOT_APPLICABLE,
                Severity.INFO,
                "No deepfake-like audio manipulation flag is present.",
                "source_evidence.deepfake_like_content_flag",
                EvidenceType.METADATA,
            )
        )

    if evidence.ai_disclosure_status == "missing":
        findings.append(
            _finding(
                "50(5)",
                FindingStatus.FAIL,
                Severity.HIGH,
                "Disclosure clarity and timeliness cannot be established because no disclosure was captured.",
                "transcript",
                EvidenceType.TRANSCRIPT,
            )
        )
    elif not disclosure_distinguishable:
        findings.append(
            _finding(
                "50(5)",
                FindingStatus.FAIL,
                Severity.MEDIUM,
                "Disclosure was detected but is not sufficiently explicit or distinguishable.",
                f"{evidence.disclosure_timestamp}s",
                EvidenceType.TRANSCRIPT,
            )
        )
    elif not disclosure_timely or disclosure_after_substantive:
        findings.append(
            _finding(
                "50(5)",
                FindingStatus.FAIL,
                Severity.MEDIUM,
                "Disclosure exists but is not timely enough to clearly inform the affected person at the start of the interaction.",
                f"{evidence.disclosure_timestamp}s",
                EvidenceType.TRANSCRIPT,
            )
        )
    else:
        findings.append(
            _finding(
                "50(5)",
                FindingStatus.PASS,
                Severity.INFO,
                "Disclosure appears timely and distinguishable.",
                f"{evidence.disclosure_timestamp}s",
                EvidenceType.TRANSCRIPT,
            )
        )

    manipulative_hits = _detect_phrase_hits(transcript, MANIPULATION_PATTERNS)
    harmful_hits = _detect_phrase_hits(transcript, HARMFUL_ADVICE_PATTERNS)
    if manipulative_hits or harmful_hits:
        hit = (manipulative_hits or harmful_hits)[0]
        findings.append(
            _finding(
                "5(1)(a)",
                FindingStatus.NEEDS_REVIEW,
                Severity.HIGH,
                f"Potential manipulative or harmful pattern detected: {hit}.",
                "transcript",
                EvidenceType.TRANSCRIPT,
                confidence=0.8,
                manual_review_required=True,
            )
        )
    else:
        findings.append(
            _finding(
                "5(1)(a)",
                FindingStatus.PASS,
                Severity.INFO,
                "No manipulative or harmful phrases were detected by the heuristic rules.",
                "transcript",
                EvidenceType.TRANSCRIPT,
                confidence=0.6,
            )
        )

    vulnerability_hits = _detect_phrase_hits(transcript, VULNERABILITY_PATTERNS)
    if vulnerability_hits:
        findings.append(
            _finding(
                "5(1)(b)",
                FindingStatus.NEEDS_REVIEW,
                Severity.HIGH,
                f"Potential exploitation of vulnerability detected: {vulnerability_hits[0]}.",
                "transcript",
                EvidenceType.TRANSCRIPT,
                confidence=0.8,
                manual_review_required=True,
            )
        )
    else:
        findings.append(
            _finding(
                "5(1)(b)",
                FindingStatus.PASS,
                Severity.INFO,
                "No vulnerability-exploitation phrases were detected by the heuristic rules.",
                "transcript",
                EvidenceType.TRANSCRIPT,
                confidence=0.6,
            )
        )

    required_docs = {
        "4": ("training_record", "Operator training evidence is linked."),
        "12": ("logging_policy", "Automatic logging evidence is linked."),
        "13": ("provider_instructions", "Provider instructions are linked."),
        "14": ("oversight_procedure", "Human oversight procedure is linked."),
        "15": ("incident_policy", "Failure and incident handling policy is linked."),
        "19": ("retention_policy", "Log retention policy is linked."),
        "26": ("deployer_notice", "Deployer notice and monitoring evidence are linked."),
        "27": ("fria", "Fundamental rights impact assessment is linked."),
    }
    governance_present = {link.document_type: link for link in payload.governance_links if link.present}
    high_risk = applicability in {Applicability.HIGH_RISK_CONFIRMED, Applicability.POTENTIAL_HIGH_RISK}
    for article, (doc_type, success_reason) in required_docs.items():
        if not high_risk and article in {"12", "13", "14", "15", "19", "26", "27"}:
            findings.append(
                _finding(
                    article,
                    FindingStatus.NOT_APPLICABLE,
                    Severity.INFO,
                    "This call is not classified as high-risk for the selected rule set.",
                    "applicability",
                    EvidenceType.SYSTEM,
                )
            )
            continue
        if doc_type in governance_present:
            if article == "14" and high_risk and not (
                payload.human_oversight_path_present or any(pattern in transcript for pattern in HUMAN_HANDOFF_PATTERNS)
            ):
                findings.append(
                    _finding(
                        article,
                        FindingStatus.FAIL,
                        Severity.HIGH,
                        "Human oversight documentation is linked, but the call record does not show an available oversight or handoff path.",
                        doc_type,
                        EvidenceType.GOVERNANCE,
                        linked_external_evidence_required=True,
                    )
                )
            else:
                findings.append(
                    _finding(
                        article,
                        FindingStatus.PASS,
                        Severity.INFO,
                        success_reason,
                        doc_type,
                        EvidenceType.GOVERNANCE,
                        linked_external_evidence_required=True,
                    )
                )
        else:
            status = FindingStatus.NOT_EVALUABLE_FROM_LOGS if article == "4" and not high_risk else FindingStatus.FAIL
            severity = Severity.MEDIUM if status == FindingStatus.NOT_EVALUABLE_FROM_LOGS else Severity.HIGH
            reason = f"Required governance evidence for Article {article} is missing: {doc_type}."
            findings.append(
                _finding(
                    article,
                    status,
                    severity,
                    reason,
                    doc_type,
                    EvidenceType.GOVERNANCE,
                    linked_external_evidence_required=True,
                )
            )

    return findings


def overall_disposition(findings: list[ComplianceFinding]) -> str:
    if any(f.status == FindingStatus.FAIL and f.severity in {Severity.CRITICAL, Severity.HIGH} for f in findings):
        return "hard_fail"
    if any(f.status == FindingStatus.FAIL for f in findings):
        return "soft_fail"
    if any(f.status == FindingStatus.NEEDS_REVIEW for f in findings):
        return "needs_review"
    return "pass"


def payload_hash(payload: AuditIngestRequest) -> str:
    blob = json.dumps(payload.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
