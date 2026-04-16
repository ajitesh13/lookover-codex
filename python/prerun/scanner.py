from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from .catalog import CONTROL_REFERENCES, MISSING_GOVERNANCE_FIELDS
from .models import ControlReference, EvidenceItem, Finding, ScanResult, SpanRecord, TraceRecord

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
}

LANGCHAIN_IMPORTS = {
    "langchain",
    "langchain_core",
    "langchain_community",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_google_genai",
}
LANGGRAPH_IMPORTS = {
    "langgraph",
    "langgraph.graph",
    "langgraph.prebuilt",
}
RISKY_PROMPTS = [
    "ignore previous instructions",
    "disregard all prior instructions",
    "reveal the system prompt",
    "show the system prompt",
    "bypass safety",
    "jailbreak",
    "dump secrets",
    "exfiltrate",
    "quote chain of thought",
    "provide hidden reasoning",
]
RISKY_CALLS = {
    "eval": "dynamic code execution",
    "exec": "dynamic code execution",
    "os.system": "shell command execution",
    "subprocess.run": "subprocess execution",
    "subprocess.Popen": "subprocess execution",
    "subprocess.call": "subprocess execution",
    "pickle.loads": "unsafe deserialization",
    "yaml.load": "unsafe yaml loading",
}
METADATA_FIELDS = {
    "ai_policy_ref",
    "ai_risk_assessment_ref",
    "ai_impact_assessment_ref",
    "human_reviewer_id",
    "disclosure_shown",
    "tools_declared_scope",
    "tools_invoked_scope",
    "data_sources",
    "agent_version",
    "model_id",
    "framework",
    "reviewer_certification_ref",
    "output_validation_result",
    "injection_scan_result",
    "system_prompt_hash",
    "embedding_provenance",
}


def scan_project(project_path: str | os.PathLike[str], strict: bool = False) -> ScanResult:
    root = Path(project_path).expanduser().resolve()
    scanned_at = datetime.now(timezone.utc).isoformat()
    files = list(_iter_python_files(root))
    file_records = [_scan_file(root, path) for path in files]

    detected_frameworks = _detect_frameworks(file_records)
    spans = [record["span"] for record in file_records]
    evidence = _dedupe_evidence([item for record in file_records for item in record["evidence"]])
    controls = _build_control_references(evidence, file_records, detected_frameworks)
    findings = _build_findings(root, file_records, evidence, detected_frameworks, strict)

    readiness_score = _readiness_score(file_records, findings, detected_frameworks)
    strict_result = _strict_mode_result(strict, findings)
    scan_id = _stable_id("scan", str(root))

    project_name = root.name or "project"
    trace_id = _stable_id("trace", str(root))
    trace = TraceRecord(
        trace_id=trace_id,
        project_path=str(root),
        project_name=project_name,
        frameworks=detected_frameworks,
        span_ids=[span.span_id for span in spans],
        metadata={
            "files_scanned": len(files),
            "python_files": len(files),
            "langchain_detected": "langchain" in detected_frameworks,
            "langgraph_detected": "langgraph" in detected_frameworks,
        },
    )

    summary = {
        "project_type": "langgraph" if "langgraph" in detected_frameworks else ("langchain" if "langchain" in detected_frameworks else "python"),
        "files_scanned": len(files),
        "python_files": len(files),
        "detected_frameworks": detected_frameworks,
        "blocking_findings": sum(1 for f in findings if f.status == "VIOLATION"),
        "advisory_findings": sum(1 for f in findings if f.status in {"GAP", "ADVISORY"}),
        "covered_controls": sum(1 for control in controls if control.evidence_fields),
    }

    return ScanResult(
        schema_version="1",
        scan_id=scan_id,
        project_path=str(root),
        scanned_at=scanned_at,
        strict_mode=strict,
        strict_result=strict_result,
        frameworks=detected_frameworks,
        readiness_score=readiness_score,
        summary=summary,
        traces=[trace],
        spans=spans,
        findings=findings,
        controls=controls,
        evidence=evidence,
    )


def scan_project_dict(project_path: str | os.PathLike[str], strict: bool = False) -> dict[str, Any]:
    return scan_project(project_path, strict=strict).to_dict()


def _iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    if not root.exists():
        return
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.name.startswith("."):
            continue
        yield path


def _scan_file(root: Path, path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        text = ""
    imports, metadata, risky_patterns, evidence, line_map = _analyze_source(root, path, text)
    span_id = _stable_id("span", f"{path}:{hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()}")
    span = SpanRecord(
        span_id=span_id,
        trace_id=_stable_id("trace", str(root)),
        parent_span_id=None,
        name=path.stem,
        kind="static-file-scan",
        file_path=str(path),
        language="python",
        imports=sorted(imports),
        metadata_fields=metadata,
        risky_patterns=sorted(set(risky_patterns)),
        evidence_ids=[item.evidence_id for item in evidence],
    )
    return {
        "path": path,
        "imports": sorted(imports),
        "metadata": metadata,
        "risky_patterns": sorted(set(risky_patterns)),
        "evidence": evidence,
        "span": span,
        "line_map": line_map,
    }


def _analyze_source(root: Path, path: Path, text: str) -> tuple[set[str], dict[str, Any], list[str], list[EvidenceItem], dict[str, int]]:
    imports: set[str] = set()
    risky_patterns: list[str] = []
    metadata: dict[str, Any] = {}
    evidence: list[EvidenceItem] = []
    line_map: dict[str, int] = {}
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                call_name = _call_name(node.func)
                if call_name in RISKY_CALLS:
                    risky_patterns.append(RISKY_CALLS[call_name])
                    evidence.append(
                        _evidence(
                            "risky-call",
                            str(path),
                            f"Detected {call_name}",
                            {"call_name": call_name, "line": getattr(node, "lineno", None)},
                        )
                    )
                for kw in node.keywords:
                    if kw.arg in METADATA_FIELDS:
                        metadata[kw.arg] = _literal_value(kw.value)
                        line_map[kw.arg] = getattr(kw.value, "lineno", getattr(node, "lineno", 1))
                        evidence.append(
                            _evidence(
                                "metadata-field",
                                str(path),
                                f"Found governance field {kw.arg}",
                                {"field": kw.arg, "value": metadata[kw.arg], "line": line_map[kw.arg]},
                            )
                        )
            elif isinstance(node, ast.Assign):
                value = _literal_value(node.value)
                for target in node.targets:
                    key = _assign_name(target)
                    if key in METADATA_FIELDS:
                        metadata[key] = value
                        line_map[key] = getattr(node, "lineno", 1)
                        evidence.append(
                            _evidence(
                                "metadata-field",
                                str(path),
                                f"Found governance field {key}",
                                {"field": key, "value": value, "line": getattr(node, "lineno", None)},
                            )
                        )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                if any(pattern in lowered for pattern in RISKY_PROMPTS):
                    risky_patterns.append("prompt-injection-like language")
                    evidence.append(
                        _evidence(
                            "risky-prompt",
                            str(path),
                            "Detected prompt text with injection language",
                            {"snippet": node.value[:240], "line": getattr(node, "lineno", None)},
                        )
                    )

    for pattern in RISKY_PROMPTS:
        if pattern in text.lower():
            risky_patterns.append(pattern)
    if "langchain" in text or any(item.startswith("langchain") for item in imports):
        evidence.append(_evidence("framework", str(path), "LangChain usage detected", {"imports": sorted(imports)}))
    if "langgraph" in text or any(item.startswith("langgraph") for item in imports):
        evidence.append(_evidence("framework", str(path), "LangGraph usage detected", {"imports": sorted(imports)}))

    metadata.setdefault("framework", "langchain" if any(item.startswith("langchain") for item in imports) else None)
    return imports, metadata, risky_patterns, evidence, line_map


def _detect_frameworks(file_records: list[dict[str, Any]]) -> list[str]:
    has_langchain = any(any(item.startswith("langchain") for item in record["imports"]) for record in file_records)
    has_langgraph = any(any(item.startswith("langgraph") for item in record["imports"]) for record in file_records)
    frameworks: list[str] = []
    if has_langchain:
        frameworks.append("langchain")
    if has_langgraph:
        frameworks.append("langgraph")
    return frameworks


def _build_control_references(
    evidence: list[EvidenceItem],
    file_records: list[dict[str, Any]],
    detected_frameworks: list[str],
) -> list[ControlReference]:
    present_fields = {key for record in file_records for key in record["metadata"].keys() if record["metadata"].get(key) not in (None, "", [], {})}
    controls: list[ControlReference] = []
    for field_name, ref in CONTROL_REFERENCES.items():
        controls.append(
            ControlReference(
                control_id=ref["control_id"],
                framework=ref["framework"],
                citation=ref["citation"],
                title=ref["title"],
                evidence_fields=[field_name] if field_name in present_fields else [],
            )
        )
    return controls


def _build_findings(
    root: Path,
    file_records: list[dict[str, Any]],
    evidence: list[EvidenceItem],
    detected_frameworks: list[str],
    strict: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    present_fields = {key for record in file_records for key in record["metadata"].keys() if record["metadata"].get(key) not in (None, "", [], {})}

    if detected_frameworks:
        for field in MISSING_GOVERNANCE_FIELDS:
            if field not in present_fields:
                ref = CONTROL_REFERENCES.get(field)
                rule_id = f"metadata.{field}"
                findings.append(
                    Finding(
                        id=_stable_id("finding", f"missing:{field}:{root}"),
                        rule_id=rule_id,
                        severity="CRITICAL" if strict else "HIGH",
                        title=f"Missing governance metadata: {field}",
                        status="VIOLATION" if strict else "GAP",
                        control_refs=[ref["control_id"]] if ref else [],
                        evidence={
                            "field": field,
                            "project_path": str(root),
                            "evidence_ids": [],
                        },
                        remediation=f"Add `{field}` to the agent metadata or runtime trace payload.",
                    )
                )

    risky_records = [record for record in file_records if record["risky_patterns"]]
    for record in risky_records:
        severity = "CRITICAL" if any("shell command execution" in item or "unsafe deserialization" in item for item in record["risky_patterns"]) else "HIGH"
        rule_id = "runtime.risky_pattern"
        findings.append(
            Finding(
                id=_stable_id("finding", f"risk:{record['path']}"),
                rule_id=rule_id,
                severity=severity,
                title="Risky code or prompt pattern detected",
                status="VIOLATION" if severity == "CRITICAL" else "GAP",
                control_refs=[
                    "OWASP-LLM01-PROMPT-INJECTION",
                    "OWASP-LLM05-OUTPUT-HANDLING",
                    "OWASP-LLM06-EXCESSIVE-AGENCY",
                ],
                evidence={
                    "file": str(record["path"]),
                    "imports": record["imports"],
                    "patterns": record["risky_patterns"],
                    "evidence_ids": [item.evidence_id for item in record["evidence"]],
                },
                file_path=str(record["path"]),
                line_start=min((item.data.get("line") or 10**9) for item in record["evidence"]) if record["evidence"] else None,
                remediation="Review the prompt, tool call, or execution path and add explicit validation or human oversight.",
            )
        )

    if not detected_frameworks:
        findings.append(
            Finding(
                id=_stable_id("finding", f"no-framework:{root}"),
                rule_id="framework.detect",
                severity="LOW",
                title="No LangChain/LangGraph usage detected",
                status="ADVISORY",
                control_refs=[],
                evidence={
                    "project_path": str(root),
                    "evidence_ids": [item.evidence_id for item in evidence[:1]],
                },
                remediation="No action required unless this repository is meant to contain an AI agent implementation.",
            )
        )
    return findings


def _readiness_score(file_records: list[dict[str, Any]], findings: list[Finding], detected_frameworks: list[str]) -> float:
    if not detected_frameworks:
        return 1.0
    score = 1.0
    for finding in findings:
        if finding.severity == "CRITICAL":
            score -= 0.22
        elif finding.severity == "HIGH":
            score -= 0.12
        elif finding.severity == "MEDIUM":
            score -= 0.06
        else:
            score -= 0.02
    if any(record["metadata"].get("tools_declared_scope") for record in file_records):
        score += 0.05
    if any(record["metadata"].get("ai_policy_ref") for record in file_records):
        score += 0.05
    return round(max(0.0, min(1.0, score)), 3)


def _strict_mode_result(strict: bool, findings: list[Finding]) -> str:
    blocking = [finding for finding in findings if finding.status == "VIOLATION"]
    if not strict:
        return "advisory"
    return "block" if blocking else "pass"


def _dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for item in items:
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        unique.append(item)
    return unique


def _evidence(kind: str, source: str, summary: str, data: dict[str, Any]) -> EvidenceItem:
    payload = json.dumps({"kind": kind, "source": source, "summary": summary, "data": data}, sort_keys=True, default=str)
    evidence_id = _stable_id("evidence", payload)
    return EvidenceItem(evidence_id=evidence_id, kind=kind, source=source, summary=summary, data=data)


def _stable_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{uuid5(NAMESPACE_URL, seed).hex[:16]}"


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return None


def _assign_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _literal_value(node.slice)
    return None


def _literal_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {
            _literal_value(key): _literal_value(value)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.List):
        return [_literal_value(item) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_value(item) for item in node.elts)
    if isinstance(node, ast.Set):
        return {_literal_value(item) for item in node.elts}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_value(node.operand)
        if isinstance(value, (int, float)):
            return -value
    return None


def serialise_scan_result(result: ScanResult) -> dict[str, Any]:
    return result.to_dict()
