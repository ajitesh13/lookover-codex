from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib import error, request
from uuid import NAMESPACE_URL, uuid4, uuid5


class RunnableLike(Protocol):
    def invoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any: ...

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any: ...


@dataclass(slots=True)
class RuntimeEvent:
    event_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    session_id: str = ""
    agent_id: str = ""
    agent_version: str = ""
    name: str = ""
    event_type: str = "runtime_event"
    status: str = "completed"
    start_time: str = ""
    end_time: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id or "",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "name": self.name,
            "event_type": self.event_type,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": dict(self.attributes),
        }


class RuntimeClient:
    def __init__(self, backend_url: str = "http://localhost:8080", timeout: float = 5.0) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.timeout = timeout

    def post_event(self, event: RuntimeEvent | dict[str, Any]) -> dict[str, Any]:
        payload = normalize_runtime_event(event)
        return self._post_json_with_fallback(["/v1/runtime/events", "/api/runtime/events"], payload)

    def post_scan(self, scan: dict[str, Any] | Any) -> dict[str, Any]:
        payload = normalize_scan_payload(scan)
        return self._post_json_with_fallback(["/v1/prerun/scans", "/api/prerun/scans"], payload)

    def _post_json_with_fallback(self, paths: list[str], payload: dict[str, Any]) -> dict[str, Any]:
        last_response: dict[str, Any] | None = None
        for path in paths:
            response = self._post_json(path, payload)
            if response.get("ok"):
                return response
            last_response = response
            if response.get("status") not in {404, 405}:
                return response
        return last_response or {"ok": False, "error": "request failed"}

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.backend_url}{path}"
        data = json.dumps(payload, default=str).encode("utf-8")
        req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return {"ok": True, "status": response.status, "body": _maybe_json(body), "url": url}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return {"ok": False, "status": exc.code, "body": _maybe_json(body), "url": url}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "url": url}


def normalize_runtime_event(event: RuntimeEvent | dict[str, Any]) -> dict[str, Any]:
    raw = event.to_dict() if isinstance(event, RuntimeEvent) else dict(event)
    attributes = dict(raw.pop("attributes", {}) or {})
    for key, value in list(raw.items()):
        if key not in {
            "trace_id",
            "span_id",
            "parent_span_id",
            "session_id",
            "agent_id",
            "agent_version",
            "name",
            "event_type",
            "status",
            "start_time",
            "end_time",
        }:
            attributes.setdefault(key, value)

    trace_id = _first_non_empty(raw.get("trace_id"), attributes.get("trace_id")) or _stable_id("trace", uuid4().hex)
    span_id = _first_non_empty(raw.get("span_id"), attributes.get("span_id")) or _stable_id("span", uuid4().hex)
    parent_span_id = _first_non_empty(raw.get("parent_span_id"), attributes.get("parent_span_id"))
    session_id = _first_non_empty(raw.get("session_id"), attributes.get("session_id"))
    agent_id = _first_non_empty(raw.get("agent_id"), attributes.get("agent_id"))
    agent_version = _first_non_empty(raw.get("agent_version"), attributes.get("agent_version"))
    name = _first_non_empty(raw.get("name"), attributes.get("name"), raw.get("event_type"), attributes.get("event_type"), "runtime_event")
    event_type = _first_non_empty(raw.get("event_type"), attributes.get("event_type"), "runtime_event")
    status = _first_non_empty(raw.get("status"), attributes.get("status"), "completed")
    start_time = _normalize_time(raw.get("start_time") or attributes.get("start_time"))
    end_time = _normalize_time(raw.get("end_time") or attributes.get("end_time")) or start_time
    attributes.setdefault("framework", _first_non_empty(attributes.get("framework"), raw.get("framework"), "langchain_or_langgraph"))
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id or "",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_version": agent_version,
        "name": name,
        "event_type": event_type,
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
        "attributes": _normalise_jsonable(attributes),
    }


def normalize_scan_payload(scan: Any) -> dict[str, Any]:
    if hasattr(scan, "to_backend_dict"):
        return scan.to_backend_dict()
    if not isinstance(scan, dict):
        scan = dict(scan)
    findings = []
    for finding in scan.get("findings", []) or []:
        if isinstance(finding, dict):
            findings.append(
                {
                    "id": finding.get("id") or finding.get("finding_id") or "",
                    "rule_id": finding.get("rule_id") or "",
                    "title": finding.get("title") or "",
                    "severity": finding.get("severity") or "",
                    "status": finding.get("status") or "",
                    "control_refs": list(finding.get("control_refs") or finding.get("control_ids") or []),
                    "evidence": dict(finding.get("evidence") or {}),
                    "remediation": finding.get("remediation") or finding.get("recommendation") or "",
                    "file_path": finding.get("file_path"),
                    "line_start": finding.get("line_start"),
                    "line_end": finding.get("line_end"),
                }
            )
    return {
        "scan_id": scan.get("scan_id") or "",
        "project_path": scan.get("project_path") or "",
        "strict_mode": bool(scan.get("strict_mode")),
        "readiness_score": scan.get("readiness_score", 0),
        "strict_result": scan.get("strict_result") or ("block" if bool(scan.get("strict_mode")) else "advisory"),
        "frameworks": list(scan.get("frameworks") or scan.get("detected_frameworks") or []),
        "summary": dict(scan.get("summary") or {}),
        "findings": findings,
    }


def create_langchain_callback_handler(
    client: RuntimeClient,
    *,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    metadata = dict(metadata or {})
    trace_id = trace_id or _stable_id("trace", uuid4().hex)
    root_span_id = span_id or _stable_id("span", uuid4().hex)
    counter = {"value": 0}

    try:
        from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
    except Exception:
        BaseCallbackHandler = object  # type: ignore[assignment]

    class _Handler(BaseCallbackHandler):  # type: ignore[misc]
        always_verbose = True

        def _emit(self, event_type: str, *, status: str = "completed", name: str | None = None, **payload: Any) -> None:
            counter["value"] += 1
            event = RuntimeEvent(
                event_id=_stable_id("event", f"{trace_id}:{event_type}:{counter['value']}:{time.time_ns()}"),
                trace_id=trace_id,
                span_id=_stable_id("span", f"{trace_id}:{event_type}:{counter['value']}"),
                parent_span_id=root_span_id if parent_span_id is None else parent_span_id,
                session_id=_first_non_empty(metadata.get("session_id")),
                agent_id=_first_non_empty(metadata.get("agent_id")),
                agent_version=_first_non_empty(metadata.get("agent_version")),
                name=name or event_type.lower(),
                event_type=event_type,
                status=status,
                start_time=_now_iso(),
                end_time=_now_iso(),
                attributes={
                    "framework": _first_non_empty(metadata.get("framework"), "langchain"),
                    "model_id": metadata.get("model_id"),
                    "model_provider": metadata.get("model_provider"),
                    "model_version": metadata.get("model_version"),
                    "tool_name": metadata.get("tool_name"),
                    **metadata,
                    **payload,
                },
            )
            client.post_event(event)

        def on_chain_start(self, serialized: Any, inputs: Any, **kwargs: Any) -> None:
            self._emit("CHAIN_START", status="started", serialized=serialized, inputs=inputs, extra=kwargs)

        def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
            self._emit("CHAIN_END", outputs=outputs, extra=kwargs)

        def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:  # type: ignore[override]
            self._emit("CHAIN_ERROR", status="error", error=str(error), extra=kwargs)

        def on_llm_start(self, serialized: Any, prompts: Any, **kwargs: Any) -> None:
            self._emit("LLM_START", status="started", serialized=serialized, prompts=prompts, extra=kwargs)

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            self._emit("LLM_END", response=response, extra=kwargs)

        def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:  # type: ignore[override]
            self._emit("LLM_ERROR", status="error", error=str(error), extra=kwargs)

        def on_tool_start(self, serialized: Any, input_str: str, **kwargs: Any) -> None:
            self._emit("TOOL_START", status="started", serialized=serialized, input=input_str, extra=kwargs)

        def on_tool_end(self, output: Any, **kwargs: Any) -> None:
            self._emit("TOOL_END", output=output, extra=kwargs)

        def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:  # type: ignore[override]
            self._emit("TOOL_ERROR", status="error", error=str(error), extra=kwargs)

        def on_agent_action(self, action: Any, **kwargs: Any) -> None:
            self._emit("AGENT_ACTION", action=str(action), extra=kwargs)

    return _Handler()


def invoke_with_runtime(
    runnable: RunnableLike,
    input: Any,
    *,
    client: RuntimeClient,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
    **kwargs: Any,
) -> Any:
    trace_id = _stable_id("trace", uuid4().hex)
    span_id = _stable_id("span", uuid4().hex)
    metadata = dict(metadata or {})
    handler = create_langchain_callback_handler(client, trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id, metadata=metadata)
    payload_config = dict(config or {})
    callbacks = list(payload_config.get("callbacks", []))
    callbacks.append(handler)
    payload_config["callbacks"] = callbacks
    _emit_runtime_event(
        client,
        "TRACE_START",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        name=name or "invoke",
        metadata=metadata,
        payload={"input": input},
    )
    try:
        result = runnable.invoke(input, config=payload_config, **kwargs)
        _emit_runtime_event(
            client,
            "TRACE_END",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name or "invoke",
            metadata=metadata,
            payload={"output": _safe_json(result)},
        )
        return result
    except Exception as exc:
        _emit_runtime_event(
            client,
            "TRACE_ERROR",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name or "invoke",
            metadata=metadata,
            payload={"error": str(exc)},
        )
        raise


async def ainvoke_with_runtime(
    runnable: RunnableLike,
    input: Any,
    *,
    client: RuntimeClient,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
    **kwargs: Any,
) -> Any:
    trace_id = _stable_id("trace", uuid4().hex)
    span_id = _stable_id("span", uuid4().hex)
    metadata = dict(metadata or {})
    handler = create_langchain_callback_handler(client, trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id, metadata=metadata)
    payload_config = dict(config or {})
    callbacks = list(payload_config.get("callbacks", []))
    callbacks.append(handler)
    payload_config["callbacks"] = callbacks
    _emit_runtime_event(
        client,
        "TRACE_START",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        name=name or "ainvoke",
        metadata=metadata,
        payload={"input": input},
    )
    try:
        result = await runnable.ainvoke(input, config=payload_config, **kwargs)
        _emit_runtime_event(
            client,
            "TRACE_END",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name or "ainvoke",
            metadata=metadata,
            payload={"output": _safe_json(result)},
        )
        return result
    except Exception as exc:
        _emit_runtime_event(
            client,
            "TRACE_ERROR",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name or "ainvoke",
            metadata=metadata,
            payload={"error": str(exc)},
        )
        raise


class LangGraphRuntimeWrapper:
    def __init__(self, graph: RunnableLike, client: RuntimeClient, *, metadata: dict[str, Any] | None = None, name: str | None = None) -> None:
        self._graph = graph
        self._client = client
        self._metadata = metadata or {}
        self._name = name or getattr(graph, "__class__", type(graph)).__name__

    def invoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return invoke_with_runtime(self._graph, input, client=self._client, name=self._name, metadata=self._metadata, config=config, **kwargs)

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return await ainvoke_with_runtime(self._graph, input, client=self._client, name=self._name, metadata=self._metadata, config=config, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._graph, item)


def wrap_langgraph(graph: RunnableLike, client: RuntimeClient, *, metadata: dict[str, Any] | None = None, name: str | None = None) -> LangGraphRuntimeWrapper:
    return LangGraphRuntimeWrapper(graph, client, metadata=metadata, name=name)


def _emit_runtime_event(
    client: RuntimeClient,
    event_type: str,
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    metadata = dict(metadata or {})
    event = RuntimeEvent(
        event_id=_stable_id("event", f"{event_type}:{time.time_ns()}"),
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        session_id=_first_non_empty(metadata.get("session_id")),
        agent_id=_first_non_empty(metadata.get("agent_id")),
        agent_version=_first_non_empty(metadata.get("agent_version")),
        name=name or event_type.lower(),
        event_type=event_type,
        status="completed",
        start_time=_now_iso(),
        end_time=_now_iso(),
        attributes={
            "framework": _first_non_empty(metadata.get("framework"), "langchain_or_langgraph"),
            **metadata,
            **dict(payload or {}),
        },
    )
    client.post_event(event)


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return str(value)


def _maybe_json(body: str) -> Any:
    try:
        return json.loads(body)
    except Exception:
        return body


def _normalise_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalise_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalise_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_normalise_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_normalise_jsonable(item) for item in sorted(value, key=lambda item: str(item))]
    return value


def _normalize_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            return value
    return _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if not isinstance(value, str):
            candidate = str(value).strip()
            if candidate:
                return candidate
    return ""


def _stable_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{uuid5(NAMESPACE_URL, seed).hex[:16]}"
