from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .runtime import RuntimeClient, RuntimeEvent, _first_non_empty, _now_iso, _stable_id


@dataclass(slots=True)
class RuntimeEventEmitter:
    """Small helper for emitting backend-normalized runtime events.

    Create one emitter per trace/span context, then call `emit(...)` for each
    event you want to post to the backend.
    """

    client: RuntimeClient
    trace_id: str
    span_id: str | None = None
    parent_span_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.span_id:
            self.span_id = _stable_id("span", uuid4().hex)

    def emit(self, event_type: str, *, name: str | None = None, status: str = "completed", **payload: Any) -> dict[str, Any]:
        event = RuntimeEvent(
            event_id=_stable_id("event", f"{self.trace_id}:{event_type}:{uuid4().hex}"),
            trace_id=self.trace_id,
            span_id=self.span_id or _stable_id("span", uuid4().hex),
            parent_span_id=self.parent_span_id,
            session_id=_first_non_empty(self.metadata.get("session_id")),
            agent_id=_first_non_empty(self.metadata.get("agent_id")),
            agent_version=_first_non_empty(self.metadata.get("agent_version")),
            name=name or event_type.lower(),
            event_type=event_type,
            status=status,
            start_time=_now_iso(),
            end_time=_now_iso(),
            attributes={**self.metadata, **payload},
        )
        return self.client.post_event(event)
