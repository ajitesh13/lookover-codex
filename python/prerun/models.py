from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ControlReference:
    control_id: str
    framework: str
    citation: str
    title: str
    evidence_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceItem:
    evidence_id: str
    kind: str
    source: str
    summary: str
    data: dict[str, Any]


@dataclass(slots=True)
class Finding:
    id: str
    rule_id: str
    title: str
    severity: str
    status: str
    control_refs: list[str]
    evidence: dict[str, Any]
    remediation: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass(slots=True)
class SpanRecord:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    kind: str
    file_path: str
    language: str
    imports: list[str]
    metadata_fields: dict[str, Any]
    risky_patterns: list[str]
    evidence_ids: list[str]


@dataclass(slots=True)
class TraceRecord:
    trace_id: str
    project_path: str
    project_name: str
    frameworks: list[str]
    span_ids: list[str]
    metadata: dict[str, Any]


@dataclass(slots=True)
class ScanResult:
    schema_version: str
    scan_id: str
    project_path: str
    scanned_at: str
    strict_mode: bool
    strict_result: str
    frameworks: list[str]
    readiness_score: float
    summary: dict[str, Any]
    traces: list[TraceRecord]
    spans: list[SpanRecord]
    findings: list[Finding]
    controls: list[ControlReference]
    evidence: list[EvidenceItem]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_backend_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "project_path": self.project_path,
            "strict_mode": self.strict_mode,
            "readiness_score": self.readiness_score,
            "strict_result": self.strict_result,
            "frameworks": self.frameworks,
            "summary": self.summary,
            "findings": [asdict(finding) for finding in self.findings],
        }
