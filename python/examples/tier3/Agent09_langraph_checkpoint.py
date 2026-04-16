"""
agent_09_langgraph_checkpointing.py
-------------------------------------
Phase 1 · Agent 9 — LangGraph ReAct Agent with Checkpointing

Same ReAct graph as Agent 08, but compiled with a MemorySaver checkpointer.
Every node execution is automatically snapshotted. A run can be resumed from
any checkpoint by passing the same thread_id.

Key concepts for audit logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  thread_id      — unique ID for a conversation thread (like session_id)
  checkpoint_id  — ID of a specific saved state snapshot
  run_id         — unique ID for a single graph.invoke() call

What your audit SDK should capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ✔ thread_id and checkpoint_id on every step
  ✔ State before and after each node
  ✔ Checkpoint save events (node completed → state persisted)
  ✔ Checkpoint restore events (run resumed from a prior checkpoint)
  ✔ Full checkpoint history for a thread

Run:
    python agent_09_langgraph_checkpointing.py
    LLM_PROVIDER=vertexai python agent_09_langgraph_checkpointing.py
    LLM_PROVIDER=googleai  python agent_09_langgraph_checkpointing.py
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
        model=os.getenv("GOOGLEAI_MODEL", "gemini-2.5-flash"),
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
        expression: A valid Python math expression, e.g. "sqrt(256) + log(100)"
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
        label: An optional label to include in the response.
    """
    now = datetime.now(timezone.utc)
    return f"Current UTC datetime: {now.strftime('%Y-%m-%d %H:%M:%S')} (label={label})"


TOOLS = [calculator, get_current_datetime]
llm_with_tools = llm.bind_tools(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  GRAPH STATE
# ═══════════════════════════════════════════════════════════════

from typing import TypedDict
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ═══════════════════════════════════════════════════════════════
#  GRAPH NODES
# ═══════════════════════════════════════════════════════════════

from langgraph.prebuilt import ToolNode

SYSTEM_MSG = SystemMessage(content=(
    "You are a helpful assistant. Use your tools when needed. "
    "Think step by step before answering."
))


def llm_node(state: AgentState) -> dict:
    messages  = [SYSTEM_MSG] + state["messages"]
    response  = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tool_node"
    return "END"


tool_node = ToolNode(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH  with MemorySaver checkpointer
# ═══════════════════════════════════════════════════════════════

import os as _os
import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

_CP_DB = _os.getenv("CHECKPOINT_DB_PATH", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "checkpoints.db"))
_conn  = sqlite3.connect(_CP_DB, check_same_thread=False)
checkpointer = SqliteSaver(_conn)
print(f"[Checkpointer] Using SQLite at {_CP_DB}")

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

graph = builder.compile(checkpointer=checkpointer)
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_09_langraph_checkpointing",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import HumanMessage


def run_agent(user_input: str, thread_id: str = "thread-001") -> dict:
    """
    Run one turn of the agent within a checkpointed thread.

    Parameters
    ----------
    user_input : str  — The human message.
    thread_id  : str  — Thread identifier. Reusing the same thread_id continues
                        the conversation from the last checkpoint.
    """
    config        = {"configurable": {"thread_id": thread_id}}
    initial_state = {"messages": [HumanMessage(content=user_input)]}

    # Capture checkpoint state BEFORE this run
    prior_checkpoint = checkpointer.get_tuple(config)
    checkpoint_id_before = prior_checkpoint.config["configurable"].get("checkpoint_id") if prior_checkpoint else None

    node_transitions = []
    tool_calls_log   = []
    checkpoint_saves = []
    cycle_count      = 0
    final_answer     = ""

    t0 = time.perf_counter()

    for step in graph.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, state_update in step.items():
            msgs = state_update.get("messages", [])

            if node_name == "llm_node":
                cycle_count += 1
                for m in msgs:
                    if hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            tool_calls_log.append({
                                "cycle":   cycle_count,
                                "tool":    tc["name"],
                                "args":    tc["args"],
                                "call_id": tc["id"],
                            })
                    else:
                        # Final LLM response (no tool calls) — extract text content
                        content = m.content
                        if isinstance(content, list):
                            final_answer = " ".join(
                                c.get("text", "") for c in content if isinstance(c, dict)
                            )
                        elif isinstance(content, str):
                            final_answer = content

            if node_name == "tool_node":
                for m in msgs:
                    tc_id   = getattr(m, "tool_call_id", None)
                    content = getattr(m, "content", "")
                    for entry in tool_calls_log:
                        if entry.get("call_id") == tc_id:
                            entry["output"] = content

            node_transitions.append({"node": node_name, "cycle": cycle_count})

            # Record each checkpoint save
            current_cp = checkpointer.get_tuple(config)
            if current_cp:
                cp_id = current_cp.config["configurable"].get("checkpoint_id")
                checkpoint_saves.append({
                    "after_node":    node_name,
                    "checkpoint_id": cp_id,
                })

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    latest_checkpoint = checkpointer.get_tuple(config)
    checkpoint_id_after = (
        latest_checkpoint.config["configurable"].get("checkpoint_id")
        if latest_checkpoint else None
    )

    _lookover.invoke(
        graph,
        initial_state,
        {"configurable": {"thread_id": f"{thread_id}-trace"}},
    )

    # Full checkpoint history for this thread (for audit trail)
    checkpoint_history = [
        {
            "checkpoint_id": cp.config["configurable"].get("checkpoint_id"),
            "ts":            cp.metadata.get("created_at", "unknown"),
            "step":          cp.metadata.get("step", -1),
        }
        for cp in checkpointer.list(config)
    ]

    return {
        "agent":               "agent_09_langgraph_checkpointing",
        "provider":            PROVIDER,
        "model":               getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "thread_id":           thread_id,
        "checkpoint_id_before": checkpoint_id_before,   # restored from
        "checkpoint_id_after":  checkpoint_id_after,    # saved to
        "input":               user_input,
        "output":              final_answer,
        "node_transitions":    node_transitions,
        "tool_calls":          tool_calls_log,
        "checkpoint_saves":    checkpoint_saves,
        "checkpoint_history":  checkpoint_history,
        "cycle_count":         cycle_count,
        "latency_ms":          latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI  — two turns on the same thread to show checkpoint continuity
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    THREAD = "demo-thread-001"

    turns = [
        sys.argv[1] if len(sys.argv) > 1 else "What is sqrt(6561) and today's date?",
        sys.argv[2] if len(sys.argv) > 2 else "Now multiply that square root result by 3.",
    ]

    for i, question in enumerate(turns, 1):
        result = run_agent(question, thread_id=THREAD)

        print(f"\n{'═' * 60}")
        print(f"  Turn {i}  |  thread={result['thread_id']}")
        print(f"{'═' * 60}")
        print(f"  Provider           : {result['provider']}  ({result['model']})")
        print(f"  Input              : {result['input']}")
        print(f"  Checkpoint before  : {result['checkpoint_id_before']}")
        print(f"  Checkpoint after   : {result['checkpoint_id_after']}")
        print(f"  Node transitions   : {[t['node'] for t in result['node_transitions']]}")
        print(f"  Tool calls         :")
        for tc in result["tool_calls"]:
            print(f"    [cycle {tc['cycle']}] {tc['tool']}({tc['args']}) → {tc.get('output','…')}")
        print(f"  Output             : {result['output']}")
        print(f"  Latency            : {result['latency_ms']} ms")
        print(f"\n  Checkpoint history ({len(result['checkpoint_history'])} snapshots):")
        for cp in result["checkpoint_history"][:5]:  # show latest 5
            print(f"    step={cp['step']}  id={str(cp['checkpoint_id'])[:16]}…")
