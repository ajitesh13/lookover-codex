"""Smoke test that publishes a scan and emits a runtime event."""

from __future__ import annotations

from prerun import RuntimeClient, RuntimeEventEmitter, scan_project


def publish_scan_and_emit_event(project_path: str, backend_url: str = "http://localhost:8080") -> dict:
    client = RuntimeClient(backend_url)
    scan = scan_project(project_path)
    scan_response = client.post_scan(scan)

    emitter = RuntimeEventEmitter(
        client,
        trace_id=scan.traces[0].trace_id,
        metadata={
            "framework": "langchain",
            "agent_version": "0.1.0",
            "model_id": "gpt-5",
        },
    )
    event_response = emitter.emit("CHAIN_START", name="backend_smoke")
    return {
        "scan_response": scan_response,
        "event_response": event_response,
    }

