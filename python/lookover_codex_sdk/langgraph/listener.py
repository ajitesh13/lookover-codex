from __future__ import annotations

import asyncio
import json as _json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from prerun.runtime import RuntimeClient

from .._common import backend_url_from_env, build_metadata

_STATE_SKIP_KEYS = {"messages", "run_id", "hop_log"}


class LookoverLangGraphListener:
    """Emit semantic LangGraph node spans to the lookover-codex runtime API."""

    _PII_PATTERNS = [
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"),
        re.compile(r"\b(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ]

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        agent_version: str | None = None,
        model_provider: str | None = None,
        model_version: str | None = None,
        base_url: str | None = None,
        session_id: str | None = None,
        **metadata: Any,
    ) -> None:
        del api_key
        self.client = RuntimeClient(backend_url_from_env(base_url))
        self.metadata = build_metadata(
            agent_id=agent_id,
            agent_version=agent_version,
            framework="langgraph",
            model_provider=model_provider,
            model_version=model_version,
            session_id=session_id,
            extra=metadata,
        )
        self.agent_id = agent_id
        self.agent_version = agent_version or ""
        self.session_id = session_id or ""
        self.model_provider = model_provider
        self.model_version = model_version

    def invoke(self, graph: Any, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
        trace_id = self._new_id("trace")
        root_span_id = self._new_id("span")
        config = config or {}

        self._emit_trace_event(
            trace_id,
            root_span_id,
            "TRACE_START",
            name=self.agent_id,
            status="started",
            payload={
                "input": self._scrub_pii(inputs),
                "root_intent": self._extract_root_intent(inputs),
                "purpose": "graph_execution",
            },
        )
        self._emit_boundary_event(
            trace_id,
            root_span_id,
            payload={"root_intent": self._extract_root_intent(inputs), "purpose": "graph_execution"},
            outcome="started",
        )

        outcome = "success"
        try:
            if self._is_async_graph(graph):
                result = asyncio.run(self._async_stream_invoke(graph, inputs, config, trace_id, root_span_id))
            else:
                result = self._stream_invoke(graph, inputs, config, trace_id, root_span_id)
            self._emit_boundary_event(
                trace_id,
                root_span_id,
                payload={"result": self._extract_result_text(result), "purpose": "graph_result"},
                outcome="success",
            )
            self._emit_trace_event(
                trace_id,
                root_span_id,
                "TRACE_END",
                name=self.agent_id,
                payload={"output": self._scrub_pii(result), "purpose": "graph_result"},
            )
            return result
        except Exception as exc:
            outcome = f"error: {type(exc).__name__}"
            self._emit_boundary_event(
                trace_id,
                root_span_id,
                payload={"error": str(exc), "purpose": "graph_result"},
                outcome=outcome,
            )
            self._emit_trace_event(
                trace_id,
                root_span_id,
                "TRACE_ERROR",
                name=self.agent_id,
                status="error",
                payload={"error": str(exc), "purpose": "graph_result"},
            )
            raise

    async def ainvoke(self, graph: Any, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
        trace_id = self._new_id("trace")
        root_span_id = self._new_id("span")
        config = config or {}

        self._emit_trace_event(
            trace_id,
            root_span_id,
            "TRACE_START",
            name=self.agent_id,
            status="started",
            payload={
                "input": self._scrub_pii(inputs),
                "root_intent": self._extract_root_intent(inputs),
                "purpose": "graph_execution",
            },
        )
        self._emit_boundary_event(
            trace_id,
            root_span_id,
            payload={"root_intent": self._extract_root_intent(inputs), "purpose": "graph_execution"},
            outcome="started",
        )

        try:
            result = await self._async_stream_invoke(graph, inputs, config, trace_id, root_span_id)
            self._emit_boundary_event(
                trace_id,
                root_span_id,
                payload={"result": self._extract_result_text(result), "purpose": "graph_result"},
                outcome="success",
            )
            self._emit_trace_event(
                trace_id,
                root_span_id,
                "TRACE_END",
                name=self.agent_id,
                payload={"output": self._scrub_pii(result), "purpose": "graph_result"},
            )
            return result
        except Exception as exc:
            outcome = f"error: {type(exc).__name__}"
            self._emit_boundary_event(
                trace_id,
                root_span_id,
                payload={"error": str(exc), "purpose": "graph_result"},
                outcome=outcome,
            )
            self._emit_trace_event(
                trace_id,
                root_span_id,
                "TRACE_ERROR",
                name=self.agent_id,
                status="error",
                payload={"error": str(exc), "purpose": "graph_result"},
            )
            raise

    def _is_async_graph(self, graph: Any) -> bool:
        return hasattr(graph, "astream") and not hasattr(graph, "_sync_stream")

    def _stream_invoke(
        self,
        graph: Any,
        inputs: dict[str, Any],
        config: dict[str, Any],
        trace_id: str,
        root_span_id: str,
    ) -> Any:
        result: Any = inputs
        try:
            for chunk in graph.stream(inputs, config):
                if not isinstance(chunk, dict):
                    continue
                for node_name, node_output in chunk.items():
                    output_dict = node_output if isinstance(node_output, dict) else {}
                    self._emit_node_span(trace_id, root_span_id, node_name, output_dict)
                    result = node_output
        except AttributeError:
            result = graph.invoke(inputs, config)
        return result

    async def _async_stream_invoke(
        self,
        graph: Any,
        inputs: dict[str, Any],
        config: dict[str, Any],
        trace_id: str,
        root_span_id: str,
    ) -> Any:
        accumulated: dict[str, Any] = dict(inputs)
        result: Any = inputs

        try:
            async for chunk in graph.astream(inputs, config, stream_mode="updates"):
                if not isinstance(chunk, dict):
                    continue
                for node_name, node_output in chunk.items():
                    output_dict = node_output if isinstance(node_output, dict) else {}
                    self._emit_node_span(trace_id, root_span_id, node_name, output_dict)
                    for key, value in output_dict.items():
                        if key == "messages" and isinstance(value, list):
                            accumulated.setdefault("messages", []).extend(value)
                        else:
                            accumulated[key] = value
                    result = output_dict
        except AttributeError:
            result = await graph.ainvoke(inputs, config)

        return accumulated if isinstance(result, dict) else result

    def _emit_trace_event(
        self,
        trace_id: str,
        span_id: str,
        event_type: str,
        *,
        name: str,
        status: str = "completed",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._post_event(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            name=name,
            event_type=event_type,
            status=status,
            payload=payload,
        )

    def _emit_boundary_event(
        self,
        trace_id: str,
        root_span_id: str,
        *,
        payload: dict[str, Any],
        outcome: str,
    ) -> None:
        self._post_event(
            trace_id=trace_id,
            span_id=self._new_id("span"),
            parent_span_id=root_span_id,
            name="DECISION",
            event_type="DECISION",
            status="started" if outcome == "started" else ("error" if outcome.startswith("error") else "completed"),
            payload=payload,
            model_output={"result": self._scrub_pii(payload)},
            node_name="decision",
        )

    def _emit_node_span(
        self,
        trace_id: str,
        root_span_id: str,
        node_name: str,
        node_update: dict[str, Any],
    ) -> None:
        after = node_update if isinstance(node_update, dict) else {}
        delta_messages = after.get("messages", [])
        msg_tool_name, msg_tool_args, msg_tool_response = self._extract_tool_call(delta_messages)
        ai_text = self._extract_ai_text(delta_messages)

        hop_tool_calls: list[dict[str, Any]] = []
        hop_log = after.get("hop_log", [])
        if hop_log and isinstance(hop_log, list):
            latest_hop = hop_log[-1]
            if isinstance(latest_hop, dict):
                raw_calls = latest_hop.get("tool_calls", []) or []
                hop_tool_calls = [item for item in raw_calls if isinstance(item, dict)]

        name_lower = node_name.lower()
        if "human" in name_lower or "interrupt" in name_lower or "handoff" in name_lower:
            event_type = "HUMAN_HANDOFF"
        elif msg_tool_name is not None or hop_tool_calls:
            event_type = "TOOL_CALL"
        elif "supervisor" in name_lower or "router" in name_lower or "planner" in name_lower:
            event_type = "DECISION"
        else:
            event_type = "MODEL_INFERENCE"

        tool_name: str | None = None
        tool_args: dict[str, Any] | None = None
        model_output: dict[str, Any] | None = None

        if msg_tool_name:
            tool_name = msg_tool_name
            tool_args = msg_tool_args
            if msg_tool_response:
                model_output = {"tool_response": self._scrub_pii(msg_tool_response)}
        elif hop_tool_calls:
            tool_name = hop_tool_calls[0].get("tool")
            tool_args = hop_tool_calls[0].get("args")
            model_output = {
                "tool_calls": self._scrub_pii(
                    [
                        {
                            "tool": call.get("tool"),
                            "args": call.get("args"),
                            "response": call.get("output", ""),
                        }
                        for call in hop_tool_calls
                    ]
                )
            }
        elif ai_text:
            model_output = {"response": self._scrub_pii(ai_text)}

        state_changes = {key: value for key, value in after.items() if key not in _STATE_SKIP_KEYS}
        state_after = self._scrub_pii(state_changes) if state_changes else None

        self._post_event(
            trace_id=trace_id,
            span_id=self._new_id("span"),
            parent_span_id=root_span_id,
            name=node_name,
            event_type=event_type,
            status="completed",
            payload={"purpose": f"node_execution:{node_name}"},
            node_name=node_name,
            tool_name=self._scrub_pii(tool_name) if tool_name else None,
            tool_args=self._scrub_pii(tool_args) if tool_args else None,
            model_output=model_output,
            state_after=state_after,
            model_provider=self.model_provider if event_type in {"MODEL_INFERENCE", "DECISION"} else None,
            model_version=self.model_version if event_type in {"MODEL_INFERENCE", "DECISION"} else None,
        )

    def _post_event(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: str,
        name: str,
        event_type: str,
        status: str,
        payload: dict[str, Any] | None = None,
        node_name: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        model_output: dict[str, Any] | None = None,
        state_after: dict[str, Any] | str | None = None,
        model_provider: str | None = None,
        model_version: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "name": name,
            "event_type": event_type,
            "status": status,
            "start_time": self._now_iso(),
            "end_time": self._now_iso(),
            "framework": "langgraph",
            **self.metadata,
        }
        if payload:
            body.update(payload)
        if node_name:
            body["node_name"] = node_name
        if tool_name:
            body["tool_name"] = tool_name
        if tool_args is not None:
            body["tool_args"] = tool_args
        if model_output is not None:
            body["model_output"] = model_output
        if state_after is not None:
            body["state_after"] = state_after
        if model_provider:
            body["model_provider"] = model_provider
        if model_version:
            body["model_id"] = model_version
            body["model_version"] = model_version
        self.client.post_event(body)

    def _extract_root_intent(self, inputs: dict[str, Any]) -> str:
        messages = inputs.get("messages", [])
        if messages:
            return self._msg_content(messages[0])[:500]
        return str(inputs)[:500]

    def _extract_result_text(self, result: Any) -> str:
        if isinstance(result, dict):
            for msg in reversed(result.get("messages", [])):
                if self._msg_role(msg) in ("ai", "assistant"):
                    return self._msg_content(msg)[:500]
        return str(result)[:500]

    def _msg_role(self, msg: Any) -> str:
        if isinstance(msg, dict):
            return msg.get("role", msg.get("type", "unknown"))
        return getattr(msg, "type", "unknown")

    def _msg_content(self, msg: Any) -> str:
        if isinstance(msg, dict):
            content = msg.get("content", "")
        else:
            content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(part.get("text", str(part)) if isinstance(part, dict) else str(part) for part in content)
        return str(content)

    def _msg_tool_calls(self, msg: Any) -> list[Any]:
        if isinstance(msg, dict):
            return msg.get("tool_calls", []) or []
        return getattr(msg, "tool_calls", None) or []

    def _extract_tool_call(self, messages: list[Any]) -> tuple[str | None, dict[str, Any] | None, str | None]:
        tool_name: str | None = None
        tool_args: dict[str, Any] | None = None
        tool_response: str | None = None

        for msg in messages:
            tool_calls = self._msg_tool_calls(msg)
            if tool_calls and tool_name is None:
                tool_call = tool_calls[0]
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args")
                else:
                    tool_name = getattr(tool_call, "name", None)
                    tool_args = getattr(tool_call, "args", None)
            if self._msg_role(msg) == "tool" and tool_response is None:
                tool_response = self._msg_content(msg)[:2000]

        return tool_name, tool_args, tool_response

    def _extract_ai_text(self, messages: list[Any]) -> str | None:
        for msg in reversed(messages):
            if self._msg_role(msg) in ("ai", "assistant") and not self._msg_tool_calls(msg):
                return self._msg_content(msg)[:3000]
        return None

    def _scrub_pii(self, data: Any) -> Any:
        if isinstance(data, str):
            value = data
            for pattern in self._PII_PATTERNS:
                value = pattern.sub("[REDACTED]", value)
            return value
        if isinstance(data, dict):
            return {key: self._scrub_pii(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._scrub_pii(item) for item in data]
        try:
            _json.dumps(data)
            return data
        except (TypeError, ValueError):
            return self._scrub_pii(str(data))

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
