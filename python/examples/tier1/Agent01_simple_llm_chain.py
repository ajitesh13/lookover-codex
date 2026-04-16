"""
agent_01_simple_llm_chain.py
-----------------------------
Phase 1 · Agent 1 — Simple LLM Chain

Single prompt → LLM → string output. No tools, no memory, no branching.

Run:
    python agent_01_simple_llm_chain.py
    LLM_PROVIDER=vertexai python agent_01_simple_llm_chain.py
    LLM_PROVIDER=googleai python agent_01_simple_llm_chain.py
"""

import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LLM SETUP  —  set LLM_PROVIDER=ollama (default) or vertexai
# ═══════════════════════════════════════════════════════════════

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

if PROVIDER == "ollama":
    from langchain_ollama import ChatOllama
    llm = ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.1.17:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        temperature=0.0,
    )

elif PROVIDER == "vertexai":
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        model_name=os.getenv("VERTEXAI_MODEL", "gemini-1.5-flash-002"),
        temperature=0.0,
    )

elif PROVIDER == "googleai":
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLEAI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )

else:
    raise ValueError(f"Unknown LLM_PROVIDER='{PROVIDER}'. Use 'ollama', 'vertexai', or 'googleai'.")

from lookover_codex_sdk.langchain import LookoverCallbackHandler

_lookover = LookoverCallbackHandler(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_01_simple_llm_chain",
    agent_version="1.0.0",
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import HumanMessage


def run_agent(user_input: str) -> dict:
    messages = [HumanMessage(content=user_input)]

    t0 = time.perf_counter()
    response = llm.invoke(messages, config={"callbacks": [_lookover]})
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        usage = {
            "input_tokens":  meta.get("input_tokens", 0),
            "output_tokens": meta.get("output_tokens", 0),
            "total_tokens":  meta.get("total_tokens", 0),
        }

    return {
        "agent":      "agent_01_simple_llm_chain",
        "provider":   PROVIDER,
        "model":      getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":      user_input,
        "output":     response.content,
        "latency_ms": latency_ms,
        "usage":      usage,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What is an AI agent? Answer in 2 sentences."

    result = run_agent(question)

    print(f"\nProvider  : {result['provider']}  ({result['model']})")
    print(f"Input     : {result['input']}")
    print(f"Output    : {result['output']}")
    print(f"Latency   : {result['latency_ms']} ms")
    print(f"Usage     : {result['usage']}\n")
