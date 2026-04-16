from __future__ import annotations

import os
from typing import Any


DEFAULT_BACKEND_URL = "http://localhost:8080"


def backend_url_from_env(base_url: str | None = None) -> str:
    return (base_url or os.getenv("LOOKOVER_BASE_URL") or DEFAULT_BACKEND_URL).rstrip("/")


def build_metadata(
    *,
    agent_id: str,
    framework: str,
    agent_version: str | None = None,
    model_provider: str | None = None,
    model_version: str | None = None,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "framework": framework,
        "agent_id": agent_id,
    }
    if agent_version:
        metadata["agent_version"] = agent_version
    if model_provider:
        metadata["model_provider"] = model_provider
    if model_version:
        metadata["model_id"] = model_version
        metadata["model_version"] = model_version
    if session_id:
        metadata["session_id"] = session_id
    for key, value in (extra or {}).items():
        if value is not None:
            metadata[key] = value
    return metadata


def infer_model_name(llm: Any) -> str:
    return getattr(llm, "model", getattr(llm, "model_name", "unknown"))
