"""
agent_08_langgraph_react.py
----------------------------
Phase 1 · Agent 8 — LangGraph ReAct Agent

Classic Reason + Act loop implemented as a LangGraph StateGraph.
The graph has two nodes:
  - llm_node  : calls the LLM (with tools bound), produces a message
  - tool_node : executes whichever tool(s) the LLM requested

Edges:
  START → llm_node
  llm_node → tool_node   (if the LLM emitted tool calls)
  llm_node → END         (if the LLM gave a final answer)
  tool_node → llm_node   (always — feeds tool results back)

What your audit SDK should capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ✔ Every node transition (llm_node → tool_node → llm_node …)
  ✔ State snapshot after each node execution
  ✔ Tool calls emitted by the LLM node (name, args)
  ✔ Tool results returned by the tool node
  ✔ Number of reasoning cycles (graph loops)
  ✔ Final answer + total latency

Run:
    python agent_08_langgraph_react.py
    LLM_PROVIDER=vertexai python agent_08_langgraph_react.py
    LLM_PROVIDER=googleai  python agent_08_langgraph_react.py
"""

import os
import time
import sys
import math
from datetime import datetime, timezone
from typing import Annotated
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
        model=os.getenv("GOOGLEAI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )

else:
    raise ValueError(f"Unknown LLM_PROVIDER='{PROVIDER}'. Use 'ollama', 'vertexai', or 'googleai'.")


# ═══════════════════════════════════════════════════════════════
#  TOOLS
# ═══════════════════════════════════════════════════════════════

from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluates a mathematical expression.
    Supports: +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e.

    Args:
        expression: A valid Python math expression, e.g. "sqrt(256) * pi"
    """
    try:
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round})
        return str(eval(expression, {"__builtins__": {}}, allowed))  # noqa: S307
    except Exception as exc:
        return f"Error: {exc}"


@tool
def get_current_datetime(label: str = "UTC") -> str:
    """
    Returns the current UTC date and time.

    Args:
        label: An optional label to include in the response (informational only).
    """
    now = datetime.now(timezone.utc)
    return f"Current UTC datetime: {now.strftime('%Y-%m-%d %H:%M:%S')} (label={label})"


TOOLS = [calculator, get_current_datetime]

# Bind tools to the LLM so it knows what it can call
llm_with_tools = llm.bind_tools(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  GRAPH STATE
# ═══════════════════════════════════════════════════════════════

from typing import TypedDict
from langchain_core.messages import BaseMessage, AnyMessage
from langgraph.graph.message import add_messages  # reducer: appends new messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ═══════════════════════════════════════════════════════════════
#  GRAPH NODES
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

SYSTEM_MSG = SystemMessage(content=(
    "You are a helpful assistant. Use your tools when needed. "
    "Think step by step before answering."
))


def llm_node(state: AgentState) -> dict:
    """Calls the LLM. The LLM either returns tool calls or a final answer."""
    messages = [SYSTEM_MSG] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """
    Routing function: if the last LLM message has tool calls → go to tool_node.
    Otherwise → END.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_node"
    return "END"


tool_node = ToolNode(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH
# ═══════════════════════════════════════════════════════════════

from langgraph.graph import StateGraph, START, END

builder = StateGraph(AgentState)
builder.add_node("llm_node",  llm_node)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "llm_node")
builder.add_conditional_edges(
    "llm_node",
    should_continue,
    {"tool_node": "tool_node", "END": END},
)
builder.add_edge("tool_node", "llm_node")

graph = builder.compile()
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_08_langraph_react",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import HumanMessage


def run_agent(user_input: str) -> dict:
    initial_state = {"messages": [HumanMessage(content=user_input)]}

    # Collect every step the graph takes for audit logging
    node_transitions = []
    tool_calls_log   = []
    cycle_count      = 0

    t0 = time.perf_counter()

    for step in graph.stream(initial_state, stream_mode="updates"):
        for node_name, state_update in step.items():
            msgs = state_update.get("messages", [])

            transition = {
                "node":          node_name,
                "messages_out":  [
                    {
                        "type":    type(m).__name__,
                        "content": getattr(m, "content", ""),
                    }
                    for m in msgs
                ],
            }

            # Log tool calls emitted by the LLM node
            if node_name == "llm_node":
                cycle_count += 1
                for m in msgs:
                    if hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            tool_calls_log.append({
                                "cycle":     cycle_count,
                                "tool":      tc["name"],
                                "args":      tc["args"],
                                "call_id":   tc["id"],
                            })

            # Log tool results from the tool node
            if node_name == "tool_node":
                for m in msgs:
                    content = getattr(m, "content", "")
                    tc_id   = getattr(m, "tool_call_id", None)
                    # Find the matching call in our log and annotate with output
                    for entry in tool_calls_log:
                        if entry.get("call_id") == tc_id:
                            entry["output"] = content

            node_transitions.append(transition)

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    # The final answer is the content of the last message
    final_state = _lookover.invoke(graph, initial_state)
    final_answer = final_state["messages"][-1].content

    return {
        "agent":            "agent_08_langgraph_react",
        "provider":         PROVIDER,
        "model":            getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":            user_input,
        "output":           final_answer,
        "node_transitions": node_transitions,
        "tool_calls":       tool_calls_log,
        "cycle_count":      cycle_count,
        "latency_ms":       latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1
        else "What is the square root of 7056, and what is today's date?"
    )

    result = run_agent(question)

    print(f"\nProvider    : {result['provider']}  ({result['model']})")
    print(f"Input       : {result['input']}")
    print(f"Cycles      : {result['cycle_count']}")

    print(f"\nNode transitions ({len(result['node_transitions'])}):")
    for t in result["node_transitions"]:
        print(f"  → {t['node']}")

    print(f"\nTool calls ({len(result['tool_calls'])}):")
    for tc in result["tool_calls"]:
        print(f"  [cycle {tc['cycle']}] {tc['tool']}({tc['args']}) → {tc.get('output', '...')}")

    print(f"\nOutput  : {result['output']}")
    print(f"Latency : {result['latency_ms']} ms\n")
