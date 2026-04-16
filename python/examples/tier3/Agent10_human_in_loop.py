"""
agent_10_human_in_the_loop.py
------------------------------
Phase 1 · Agent 10 — Human-in-the-Loop Agent

The graph pauses BEFORE executing a tool and waits for a human to approve
or reject the tool call. This is implemented with LangGraph's interrupt()
mechanism:

  Flow:
    START → llm_node → approval_gate (interrupt) → tool_node → llm_node → …

  approval_gate node:
    - Inspects the pending tool call from the LLM
    - Calls interrupt() which raises GraphInterrupt and suspends the graph
    - When the graph is resumed with Command(resume=...), this node checks
      the human's decision: "approve" → continues, "reject" → injects a
      refusal ToolMessage back so the LLM can respond gracefully

What your audit SDK should capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ✔ INTERRUPT event  — which tool was pending, what args were requested
  ✔ Human decision   — "approve" | "reject" + optional reason
  ✔ RESUME event     — graph restarted from the interrupt checkpoint
  ✔ Whether the tool actually executed or was blocked
  ✔ Time spent waiting for human approval (approval_latency_ms)
  ✔ Full audit trail: llm_call → interrupt → human_decision → tool_exec → llm_call

Run:
    python agent_10_human_in_the_loop.py
    LLM_PROVIDER=vertexai python agent_10_human_in_the_loop.py
    LLM_PROVIDER=googleai  python agent_10_human_in_the_loop.py
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
        expression: e.g. "sqrt(256) + log(1000)"
    """
    try:
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round})
        return str(eval(expression, {"__builtins__": {}}, allowed))  # noqa: S307
    except Exception as exc:
        return f"Error: {exc}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    Sends an email (simulated — no real email is sent).

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Email body content.
    """
    # Simulated — in a real system this would call an SMTP / SendGrid API
    return f"[SIMULATED] Email sent to={to!r}  subject={subject!r}  body_length={len(body)}"


TOOLS      = [calculator, send_email]
TOOLS_MAP  = {t.name: t for t in TOOLS}
llm_with_tools = llm.bind_tools(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  GRAPH STATE
# ═══════════════════════════════════════════════════════════════

from typing import TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ═══════════════════════════════════════════════════════════════
#  GRAPH NODES
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command

SYSTEM_MSG = SystemMessage(content=(
    "You are a helpful assistant. You have access to a calculator and an email tool. "
    "Use them when appropriate."
))


def llm_node(state: AgentState) -> dict:
    messages = [SYSTEM_MSG] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def approval_gate(state: AgentState) -> Command:
    """
    Inspects pending tool calls and interrupts execution for human approval.
    When resumed, routes to tool execution (approve) or injects a refusal (reject).
    """
    last_msg = state["messages"][-1]

    if not (hasattr(last_msg, "tool_calls") and last_msg.tool_calls):
        # No tool calls — nothing to approve, go straight to END routing
        return Command(goto="llm_node")

    # Take the first pending tool call (one approval gate per tool call)
    tc = last_msg.tool_calls[0]

    # ── INTERRUPT: suspend and surface the pending tool call to the human ──
    human_decision = interrupt({
        "pending_tool":  tc["name"],
        "pending_args":  tc["args"],
        "call_id":       tc["id"],
        "message":       f"Agent wants to call '{tc['name']}' with args {tc['args']}. Approve?",
    })
    # ── RESUME: graph restarts here with human_decision as the resume value ──

    decision = human_decision.get("decision", "approve").lower()
    reason   = human_decision.get("reason", "")

    if decision == "approve":
        # Let the tool node execute normally
        return Command(goto="tool_node")
    else:
        # Inject a refusal ToolMessage so the LLM can respond gracefully
        refusal = ToolMessage(
            tool_call_id=tc["id"],
            content=f"Tool call rejected by human. Reason: {reason or 'no reason given'}",
        )
        return Command(goto="llm_node", update={"messages": [refusal]})


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "approval_gate"
    return "END"


tool_node = ToolNode(TOOLS)


# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH  (checkpointer required for interrupt/resume)
# ═══════════════════════════════════════════════════════════════

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

builder = StateGraph(AgentState)
builder.add_node("llm_node",      llm_node)
builder.add_node("approval_gate", approval_gate)
builder.add_node("tool_node",     tool_node)

builder.add_edge(START, "llm_node")
builder.add_conditional_edges(
    "llm_node",
    should_continue,
    {"approval_gate": "approval_gate", "END": END},
)
builder.add_edge("tool_node", "llm_node")

graph = builder.compile(checkpointer=checkpointer)
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_10_human_in_loop",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT  — run_agent orchestrates the interrupt/resume cycle
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphInterrupt


def run_agent(
    user_input:       str,
    thread_id:        str  = "hitl-thread-001",
    auto_approve:     bool = True,
    rejection_tools:  list[str] | None = None,
) -> dict:
    """
    Run the human-in-the-loop agent.

    Parameters
    ----------
    user_input      : The human message.
    thread_id       : Checkpoint thread identifier.
    auto_approve    : If True, approves all tool calls automatically (for testing).
    rejection_tools : List of tool names to auto-reject (for testing the reject path).
    """
    rejection_tools = rejection_tools or []
    config          = {"configurable": {"thread_id": thread_id}}
    initial_state   = {"messages": [HumanMessage(content=user_input)]}

    audit_log = {
        "agent":        "agent_10_human_in_the_loop",
        "provider":     PROVIDER,
        "model":        getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "thread_id":    thread_id,
        "input":        user_input,
        "output":       None,
        "interrupts":   [],          # each approval gate event
        "tool_calls":   [],          # tools that were actually executed
        "latency_ms":   0,
    }

    t_total = time.perf_counter()
    current_input = initial_state

    while True:
        try:
            # Stream until completion or interrupt
            final_state = None
            for step in graph.stream(current_input, config=config, stream_mode="updates"):
                final_state = step

            # Graph completed without interruption
            state     = _lookover.invoke(graph, current_input, config)
            final_msg = state["messages"][-1]
            audit_log["output"] = final_msg.content

            # Collect tool call details from messages
            for msg in state["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        audit_log["tool_calls"].append({
                            "tool": tc["name"],
                            "args": tc["args"],
                        })
            break

        except GraphInterrupt as interrupt_exc:
            # The approval_gate node fired interrupt()
            interrupt_payload = interrupt_exc.args[0] if interrupt_exc.args else {}

            # Handle list of interrupt values (LangGraph wraps them)
            if isinstance(interrupt_payload, list) and interrupt_payload:
                interrupt_payload = interrupt_payload[0].value if hasattr(interrupt_payload[0], "value") else {}

            pending_tool = interrupt_payload.get("pending_tool", "unknown")
            t_interrupt  = time.perf_counter()

            # Decide: approve or reject
            if pending_tool in rejection_tools:
                decision = "reject"
                reason   = f"Tool '{pending_tool}' is on the rejection list."
            else:
                decision = "approve"
                reason   = "Auto-approved."

            approval_latency_ms = round((time.perf_counter() - t_interrupt) * 1000, 2)

            audit_log["interrupts"].append({
                "pending_tool":       pending_tool,
                "pending_args":       interrupt_payload.get("pending_args", {}),
                "call_id":            interrupt_payload.get("call_id", ""),
                "decision":           decision,
                "reason":             reason,
                "approval_latency_ms": approval_latency_ms,
            })

            # Resume the graph with the human decision
            current_input = Command(
                resume={"decision": decision, "reason": reason}
            )

    audit_log["latency_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
    return audit_log


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uuid

    print("\n" + "═" * 60)
    print("  Scenario 1 — All tools APPROVED")
    print("═" * 60)
    r1 = run_agent(
        user_input   = "Calculate sqrt(9801) and also send an email to bob@example.com with subject 'Result' and the answer as the body.",
        thread_id    = f"hitl-{uuid.uuid4().hex[:8]}",
        auto_approve = True,
    )
    print(f"  Provider   : {r1['provider']}  ({r1['model']})")
    print(f"  Input      : {r1['input']}")
    print(f"  Interrupts : {len(r1['interrupts'])}")
    for ir in r1["interrupts"]:
        print(f"    → gate: tool={ir['pending_tool']}  decision={ir['decision']}  approval_ms={ir['approval_latency_ms']}")
    print(f"  Tool calls : {[tc['tool'] for tc in r1['tool_calls']]}")
    print(f"  Output     : {r1['output']}")
    print(f"  Latency    : {r1['latency_ms']} ms")

    print("\n" + "═" * 60)
    print("  Scenario 2 — send_email REJECTED")
    print("═" * 60)
    r2 = run_agent(
        user_input      = "Send an email to alice@example.com saying hello, and calculate 42 * 99.",
        thread_id       = f"hitl-{uuid.uuid4().hex[:8]}",
        auto_approve    = True,
        rejection_tools = ["send_email"],
    )
    print(f"  Provider   : {r2['provider']}  ({r2['model']})")
    print(f"  Input      : {r2['input']}")
    print(f"  Interrupts : {len(r2['interrupts'])}")
    for ir in r2["interrupts"]:
        print(f"    → gate: tool={ir['pending_tool']}  decision={ir['decision']}  reason={ir['reason']}")
    print(f"  Output     : {r2['output']}")
    print(f"  Latency    : {r2['latency_ms']} ms\n")
