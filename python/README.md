# `prerun` Python Guide

This directory contains the Python-side pre-run scanner and runtime SDK for `lookover-codex`.

## Install / run locally

From `python/`:

```bash
python3 -m prerun.cli --help
```

## Pre-run scan

Scan a project and write backend-ready JSON:

```bash
python3 -m prerun.cli scan /path/to/project --output ./scan.json
```

Tier 4 demo example now included in this repo:

```bash
python3 -m prerun.cli scan /Users/ajitesh/lookover-codex/python/examples/tier4/agent12_supervisor.py --output ./agent12_scan.json
```

Strict mode exits non-zero when blocking findings are present:

```bash
python3 -m prerun.cli scan /path/to/project --strict --output ./scan.json
```

```bash
python3 -m prerun.cli scan /Users/ajitesh/lookover-codex/python/examples/tier4/agent12_supervisor.py --strict --output ./agent12_strict_scan.json
```

The scan output is shaped for the Go backend and includes:

- `scan_id`
- `project_path`
- `strict_mode`
- `strict_result`
- `frameworks`
- `readiness_score`
- `summary`
- `findings`

## Publish a scan

Send a saved scan JSON file to the backend:

```bash
python3 -m prerun.cli publish ./scan.json --backend-url http://localhost:8080
```

The client prefers `/v1/prerun/scans` and falls back to `/api/prerun/scans` if needed.

## Backend smoke test

If you want a quick end-to-end check, the example below scans a project, publishes the backend-ready payload, and posts a runtime event:

```python
from prerun import RuntimeClient, RuntimeEventEmitter, scan_project

client = RuntimeClient("http://localhost:8080")
scan = scan_project("/path/to/project")
client.post_scan(scan)

emitter = RuntimeEventEmitter(
    client,
    trace_id=scan.traces[0].trace_id,
    metadata={"framework": "langchain", "agent_version": "0.1.0"},
)
emitter.emit("CHAIN_START", name="demo")
```

## Runtime instrumentation

Use `RuntimeClient` plus the LangChain callback handler or LangGraph wrapper helpers.

### LangChain

```python
from prerun.runtime import RuntimeClient, create_langchain_callback_handler

client = RuntimeClient("http://localhost:8080")
handler = create_langchain_callback_handler(
    client,
    metadata={
        "framework": "langchain",
        "agent_version": "0.1.0",
        "model_id": "gpt-5",
    },
)

# Pass `handler` in the LangChain callbacks list.
```

### LangGraph

```python
from prerun.runtime import RuntimeClient, wrap_langgraph

client = RuntimeClient("http://localhost:8080")
wrapped_graph = wrap_langgraph(graph, client, metadata={"framework": "langgraph"})

result = wrapped_graph.invoke(input_payload)
```

### Direct event posting

`RuntimeClient.post_event()` normalizes payloads toward the Go API contract:

- top-level `trace_id`, `span_id`, `parent_span_id`
- `session_id`, `agent_id`, `agent_version`, `name`, `event_type`, `status`
- `start_time`, `end_time`
- extra fields stored under `attributes`
