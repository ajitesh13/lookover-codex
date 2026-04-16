"""Minimal examples for the pre-run scanner and runtime client."""

from __future__ import annotations

import json
from pathlib import Path

from prerun.cli import main as prerun_main
from prerun.runtime import RuntimeClient, RuntimeEvent, wrap_langgraph
from prerun.scanner import scan_project


def run_scan(project_path: str, output_path: str) -> dict:
    result = scan_project(project_path)
    payload = result.to_backend_dict()
    Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def publish_scan(scan_path: str, backend_url: str = "http://localhost:8080") -> None:
    client = RuntimeClient(backend_url)
    scan = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    client.post_scan(scan)


def record_runtime_event(backend_url: str = "http://localhost:8080") -> dict:
    client = RuntimeClient(backend_url)
    return client.post_event(
        RuntimeEvent(
            event_id="evt_demo",
            trace_id="trace_demo",
            span_id="span_demo",
            name="demo",
            event_type="CHAIN_START",
            attributes={
                "framework": "langchain",
                "agent_version": "0.1.0",
                "model_id": "gpt-5",
            },
        )
    )


def instrument_langgraph(graph, backend_url: str = "http://localhost:8080"):
    client = RuntimeClient(backend_url)
    return wrap_langgraph(graph, client, metadata={"framework": "langgraph", "agent_version": "0.1.0"})


if __name__ == "__main__":
    raise SystemExit(prerun_main())
