from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PYTHON_ROOT = ROOT.parent
DEFAULT_ARTIFACTS_DIR = ROOT / "artifacts"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from prerun.scanner import scan_project


@dataclass(frozen=True)
class RuntimeCall:
    label: str
    function_name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentSpec:
    slug: str
    file_path: Path
    runtime_calls: tuple[RuntimeCall, ...]


def _specs() -> tuple[AgentSpec, ...]:
    return (
        AgentSpec(
            slug="tier1_agent01_simple_llm_chain",
            file_path=ROOT / "tier1" / "Agent01_simple_llm_chain.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("What is an AI agent? Answer in 2 sentences.",)),),
        ),
        AgentSpec(
            slug="tier1_agent02_prompt_template",
            file_path=ROOT / "tier1" / "Agent02_prompt_template.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("transformer neural networks", "beginner")),),
        ),
        AgentSpec(
            slug="tier1_agent03_output_parser",
            file_path=ROOT / "tier1" / "Agent03_output_parser.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Retrieval-Augmented Generation",)),),
        ),
        AgentSpec(
            slug="tier2_agent04_single_tool",
            file_path=ROOT / "tier2" / "Agent04_single_tool.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("What is the square root of 1764 multiplied by the log of 1000?",)),),
        ),
        AgentSpec(
            slug="tier2_agent05_multi_tool",
            file_path=ROOT / "tier2" / "Agent05_multi_tool.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Count the words in 'LangGraph improves traceability' and convert 12 miles to kilometers.",)),),
        ),
        AgentSpec(
            slug="tier2_agent06_rag",
            file_path=ROOT / "tier2" / "Agent06_rag.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("What is LangGraph and how does it differ from LangChain?",)),),
        ),
        AgentSpec(
            slug="tier2_agent07_conversational_memory",
            file_path=ROOT / "tier2" / "Agent07_conversational_memory.py",
            runtime_calls=(
                RuntimeCall("turn1", "run_turn", ("Hi! My name is Alex and I'm building an AI audit logging SDK.",), {"session_id": "spec-session-007"}),
                RuntimeCall("turn2", "run_turn", ("What are the most important events I should log for an LLM call?",), {"session_id": "spec-session-007"}),
                RuntimeCall("turn3", "run_turn", ("Can you summarise what you know about me and what we discussed?",), {"session_id": "spec-session-007"}),
            ),
        ),
        AgentSpec(
            slug="tier3_agent08_langraph_react",
            file_path=ROOT / "tier3" / "Agent08_langraph_react.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("What is sqrt(1764) and what is the current UTC date?",)),),
        ),
        AgentSpec(
            slug="tier3_agent09_langraph_checkpoint",
            file_path=ROOT / "tier3" / "Agent09_langraph_checkpoint.py",
            runtime_calls=(
                RuntimeCall("turn1", "run_agent", ("What is sqrt(6561) and today's date?",), {"thread_id": "spec-thread-009"}),
                RuntimeCall("turn2", "run_agent", ("Now multiply that square root result by 3.",), {"thread_id": "spec-thread-009"}),
            ),
        ),
        AgentSpec(
            slug="tier3_agent10_human_in_loop",
            file_path=ROOT / "tier3" / "Agent10_human_in_loop.py",
            runtime_calls=(
                RuntimeCall(
                    "approve",
                    "run_agent",
                    ("Calculate sqrt(9801) and also send an email to bob@example.com with subject 'Result' and the answer as the body.",),
                    {"thread_id": "spec-hitl-approve", "auto_approve": True},
                ),
                RuntimeCall(
                    "reject",
                    "run_agent",
                    ("Send an email to alice@example.com saying hello, and calculate 42 * 99.",),
                    {"thread_id": "spec-hitl-reject", "auto_approve": True, "rejection_tools": ["send_email"]},
                ),
            ),
        ),
        AgentSpec(
            slug="tier3_agent11_subgraph",
            file_path=ROOT / "tier3" / "Agent11_subgraph.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Explain how LangGraph subgraphs work and why they are useful for audit logging.",)),),
        ),
        AgentSpec(
            slug="tier4_agent12_supervisor",
            file_path=ROOT / "tier4" / "agent12_supervisor.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Calculate sqrt(98596), get the current UTC datetime, then write a concise summary of both findings.",)),),
        ),
        AgentSpec(
            slug="tier4_agent13_hierarchical",
            file_path=ROOT / "tier4" / "Agent13_ hierarchical.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Calculate log(1000000), get the current UTC datetime, then write and edit a concise summary covering both findings.",)),),
        ),
        AgentSpec(
            slug="tier4_agent14_parallel",
            file_path=ROOT / "tier4" / "Agent14_parallel.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("What is the current UTC datetime, what is sqrt(12321), and why do AI agents need audit logs?",)),),
        ),
        AgentSpec(
            slug="tier4_agent15_collaborative",
            file_path=ROOT / "tier4" / "Agent15_collaborative.py",
            runtime_calls=(RuntimeCall("default", "run_agent", ("Write and refine a balanced 3-paragraph article about why audit trails matter for AI agents in production.",), {"max_rounds": 2}),),
        ),
    )


def _load_module(slug: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(slug, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module for {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def run_scans(artifacts_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in _specs():
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            scan = scan_project(str(spec.file_path)).to_backend_dict()
            record = {
                "slug": spec.slug,
                "status": "ok",
                "started_at": started_at,
                "file_path": str(spec.file_path),
                "scan_path": str(artifacts_dir / "scans" / f"{spec.slug}.json"),
            }
            _write_json(artifacts_dir / "scans" / f"{spec.slug}.json", scan)
        except Exception as exc:  # pragma: no cover - operational path
            record = {
                "slug": spec.slug,
                "status": "error",
                "started_at": started_at,
                "file_path": str(spec.file_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(record)
    _write_json(artifacts_dir / "scan_summary.json", results)
    return results


def run_runtime_specs(artifacts_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in _specs():
        for call in spec.runtime_calls:
            started_at = datetime.now(timezone.utc).isoformat()
            record = {
                "slug": spec.slug,
                "label": call.label,
                "started_at": started_at,
                "file_path": str(spec.file_path),
                "function_name": call.function_name,
            }
            try:
                module = _load_module(f"{spec.slug}_{call.label}", spec.file_path)
                func = getattr(module, call.function_name)
                result = func(*call.args, **(call.kwargs or {}))
                output_path = artifacts_dir / "runs" / spec.slug / f"{call.label}.json"
                _write_json(output_path, result)
                record.update({"status": "ok", "output_path": str(output_path)})
            except Exception as exc:  # pragma: no cover - operational path
                error_payload = {
                    "slug": spec.slug,
                    "label": call.label,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                output_path = artifacts_dir / "runs" / spec.slug / f"{call.label}.json"
                _write_json(output_path, error_payload)
                record.update({"status": "error", "error": error_payload["error"], "output_path": str(output_path)})
            results.append(record)
    _write_json(artifacts_dir / "run_summary.json", results)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-scan checks and runtime agent specs for copied lookover-codex examples.")
    parser.add_argument("--backend-url", default="http://localhost:8080", help="Backend URL used by the runtime SDK.")
    parser.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR), help="Directory for scan and runtime artifacts.")
    parser.add_argument("--skip-scans", action="store_true", help="Skip static pre-scan checks.")
    parser.add_argument("--skip-runs", action="store_true", help="Skip runtime spec execution.")
    args = parser.parse_args()

    os.environ.setdefault("LOOKOVER_BASE_URL", args.backend_url)
    os.environ.setdefault("LLM_PROVIDER", "ollama")

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": args.backend_url,
        "artifacts_dir": str(artifacts_dir),
    }
    if not args.skip_scans:
        summary["scans"] = run_scans(artifacts_dir)
    if not args.skip_runs:
        summary["runs"] = run_runtime_specs(artifacts_dir)
    _write_json(artifacts_dir / "summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
