"""
agent_04_single_tool.py
------------------------
Phase 1 · Agent 4 — Single Tool Agent

Agent with one tool (calculator). The LLM decides when to call it,
the AgentExecutor runs the tool, and the result feeds back into the LLM
for a final answer.

Run:
    python agent_04_single_tool.py
    LLM_PROVIDER=vertexai python agent_04_single_tool.py
    LLM_PROVIDER=googleai python agent_04_single_tool.py
"""

import os
import time
import sys
import math
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LLM SETUP  —  set LLM_PROVIDER=ollama (default) / vertexai / googleai
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
        model=os.getenv("GOOGLEAI_MODEL", "gemini-2.5-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )

else:
    raise ValueError(f"Unknown LLM_PROVIDER='{PROVIDER}'. Use 'ollama', 'vertexai', or 'googleai'.")


# ═══════════════════════════════════════════════════════════════
#  TOOL DEFINITION
# ═══════════════════════════════════════════════════════════════

from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluates a mathematical expression and returns the result.
    Supports: +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e.

    Args:
        expression: A valid Python math expression as a string, e.g. "sqrt(144) + 2**8"
    """
    try:
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed_names.update({"abs": abs, "round": round})
        result = eval(expression, {"__builtins__": {}}, allowed_names)  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"Error evaluating expression: {exc}"


TOOLS = [calculator]


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from lookover_codex_sdk import RuntimeClient, invoke_with_runtime

agent = create_agent(
    llm,
    TOOLS,
    system_prompt=(
        "You are a helpful assistant with access to a calculator tool. "
        "Use the calculator for any arithmetic or mathematical questions."
    ),
)

_runtime_client = RuntimeClient(os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"))


def run_agent(user_input: str) -> dict:
    t0     = time.perf_counter()
    result = invoke_with_runtime(
        agent,
        {"messages": [("human", user_input)]},
        client=_runtime_client,
        name="agent_04_single_tool",
        metadata={
            "framework": "langchain",
            "agent_id": "agent_04_single_tool",
            "agent_version": "1.0.0",
            "model_provider": PROVIDER,
            "model_id": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "model_version": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        },
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    messages = result["messages"]

    # Pair AIMessage tool_calls with their ToolMessage results
    tool_calls = []
    tool_results: dict[str, str] = {
        m.tool_call_id: m.content
        for m in messages if isinstance(m, ToolMessage)
    }
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                tool_calls.append({
                    "tool":        tc["name"],
                    "tool_input":  tc["args"],
                    "tool_output": tool_results.get(tc["id"], ""),
                })

    output = messages[-1].content

    return {
        "agent":      "agent_04_single_tool",
        "provider":   PROVIDER,
        "model":      getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":      user_input,
        "output":     output,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1
        else "What is the square root of 1764 multiplied by the log of 1000?"
    )

    result = run_agent(question)

    print(f"\nProvider   : {result['provider']}  ({result['model']})")
    print(f"Input      : {result['input']}")
    print(f"Tool calls :")
    for tc in result["tool_calls"]:
        print(f"  → tool={tc['tool']}  input={tc['tool_input']}  output={tc['tool_output']}")
    print(f"Output     : {result['output']}")
    print(f"Latency    : {result['latency_ms']} ms\n")
