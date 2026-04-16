from __future__ import annotations

from typing import Any

from prerun.runtime import RuntimeClient, create_langchain_callback_handler

from .._common import backend_url_from_env, build_metadata


class LookoverCallbackHandler:
    """Compatibility constructor for LangChain callback usage in copied examples."""

    def __new__(
        cls,
        api_key: str,
        agent_id: str,
        agent_version: str | None = None,
        base_url: str | None = None,
        model_provider: str | None = None,
        model_version: str | None = None,
        session_id: str | None = None,
        **metadata: Any,
    ):
        del api_key
        client = RuntimeClient(backend_url_from_env(base_url))
        return create_langchain_callback_handler(
            client,
            metadata=build_metadata(
                agent_id=agent_id,
                agent_version=agent_version,
                framework="langchain",
                model_provider=model_provider,
                model_version=model_version,
                session_id=session_id,
                extra=metadata,
            ),
        )
