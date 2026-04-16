from __future__ import annotations

from typing import Any

from prerun.runtime import RuntimeClient, wrap_langgraph

from .._common import backend_url_from_env, build_metadata


class LookoverLangGraphListener:
    """Compatibility wrapper that instruments LangGraph runs for lookover-codex."""

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

    def invoke(self, graph: Any, inputs: Any, config: dict[str, Any] | None = None) -> Any:
        wrapped = wrap_langgraph(graph, self.client, metadata=self.metadata, name=self.metadata.get("agent_id"))
        return wrapped.invoke(inputs, config)

    async def ainvoke(self, graph: Any, inputs: Any, config: dict[str, Any] | None = None) -> Any:
        wrapped = wrap_langgraph(graph, self.client, metadata=self.metadata, name=self.metadata.get("agent_id"))
        return await wrapped.ainvoke(inputs, config)
