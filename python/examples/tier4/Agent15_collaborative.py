"""
agent_15_collaborative.py
--------------------------
Phase 1 · Agent 15 — Collaborative Research Agent System

Four agents collaborate via a shared message board across multiple rounds.
All tool calls are real — no shared module, no mocking.

Agents & their tools:
  planner    : pure LLM — orchestrates rounds, decides when done
  researcher : wikipedia_search + web_search
  critic     : web_search (finds counterarguments)
  writer     : write_file + read_file (real disk I/O)

Flow per round: planner → researcher → critic → writer → planner (repeat or END)
Final document is saved to /tmp/agent15_draft.txt after every writer turn.

Run:
    python agent_15_collaborative.py
    LLM_PROVIDER=vertexai python agent_15_collaborative.py
    LLM_PROVIDER=googleai  python agent_15_collaborative.py
"""

import os
import sys
import time
import uuid
import json
import math
from datetime import datetime, timezone
from typing import Annotated, TypedDict
from urllib import request as url_request, parse as url_parse, error as url_error
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LLM SETUP
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
def wikipedia_search(query: str) -> str:
    """
    Search Wikipedia and return the opening summary of the best matching article.
    Uses the MediaWiki REST API — no API key required.
    Args:
        query: The search term, e.g. "LangChain AI framework"
    """
    try:
        with url_request.urlopen(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={url_parse.quote(query)}&srlimit=1&format=json", timeout=10
        ) as resp:
            results = json.loads(resp.read()).get("query", {}).get("search", [])
        if not results:
            return f"No Wikipedia article found for: {query}"
        title = results[0]["title"]
        with url_request.urlopen(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{url_parse.quote(title)}",
            timeout=10,
        ) as resp:
            page = json.loads(resp.read())
        url = page.get("content_urls", {}).get("desktop", {}).get("page", "")
        return f"[Wikipedia: {title}]\n{page.get('extract', 'No extract.')}\nSource: {url}"
    except (url_error.URLError, url_error.HTTPError) as exc:
        raise RuntimeError(f"Wikipedia API error: {exc}") from exc


@tool
def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo Instant Answer API. No API key required.
    Args:
        query: The search query
    """
    try:
        req = url_request.Request(
            f"https://api.duckduckgo.com/?q={url_parse.quote(query)}&format=json&no_html=1&skip_disambig=1",
            headers={"User-Agent": "AuditSDK-Agent/1.0"},
        )
        with url_request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        abstract = data.get("Abstract", "").strip()
        if abstract:
            return f"{abstract}\nSource: {data.get('AbstractURL', '')}"
        topics = [t["Text"] for t in data.get("RelatedTopics", [])[:3]
                  if isinstance(t, dict) and t.get("Text")]
        return "\n\n".join(topics) if topics else f"No instant answer found for: {query}"
    except (url_error.URLError, url_error.HTTPError) as exc:
        raise RuntimeError(f"DuckDuckGo API error: {exc}") from exc


@tool
def read_file(path: str) -> str:
    """
    Reads and returns the text content of a local file.
    Args:
        path: File path, e.g. "/tmp/notes.txt"
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"[File: {path}  size={len(content)} chars]\n{content}"
    except FileNotFoundError:
        raise RuntimeError(f"File not found: {path}")
    except Exception as exc:
        raise RuntimeError(f"File read error: {exc}") from exc


@tool
def write_file(path: str, content: str) -> str:
    """
    Writes text content to a local file (creates or overwrites).
    Args:
        path   : File path, e.g. "/tmp/output.txt"
        content: Text to write.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as exc:
        raise RuntimeError(f"File write error: {exc}") from exc


# ═══════════════════════════════════════════════════════════════
#  TOOL GROUPS & CONSTANTS
# ═══════════════════════════════════════════════════════════════

from langgraph.prebuilt import ToolNode
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph.message import add_messages

RESEARCHER_TOOLS = [wikipedia_search, web_search]
CRITIC_TOOLS     = [web_search]
WRITER_TOOLS     = [write_file, read_file]
OUTPUT_FILE      = "/tmp/agent15_draft.txt"

# ═══════════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════════


def react_loop(system: str, user: str, tools: list, max_iters: int = 5) -> tuple[str, list[dict]]:
    """Run a ReAct loop. Returns (final_text, tool_calls_log)."""
    bound_llm  = llm.bind_tools(tools)
    tool_node  = ToolNode(tools)
    messages   = [SystemMessage(content=system), HumanMessage(content=user)]
    tc_log     = []
    for _ in range(max_iters):
        response = bound_llm.invoke(messages)
        messages.append(response)
        if not getattr(response, "tool_calls", None):
            break
        tool_results = tool_node.invoke({"messages": [response]})
        for tm in tool_results.get("messages", []):
            messages.append(tm)
            tc_id   = getattr(tm, "tool_call_id", None)
            matched = next((tc for tc in response.tool_calls if tc["id"] == tc_id), {})
            tc_log.append({"tool": matched.get("name","?"), "args": matched.get("args",{}),
                           "output": getattr(tm, "content", "")[:300]})
    return getattr(messages[-1], "content", "") or "", tc_log


# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════


class CollabState(TypedDict):
    messages:       Annotated[list[AnyMessage], add_messages]
    original_task:  str
    current_round:  int
    max_rounds:     int
    planner_done:   bool
    current_draft:  str
    span_log:       list[dict]


# ═══════════════════════════════════════════════════════════════
#  GRAPH NODES
# ═══════════════════════════════════════════════════════════════

from langgraph.graph import StateGraph, START, END

PLANNER_SYS = (
    "You are the Planner for a collaborative writing team.\n"
    "At round start: write a short focus/goal for this round in plain text.\n"
    "At round end (when asked to decide): respond ONLY with JSON:\n"
    '{"continue": true/false, "reason": "<one sentence>"}'
)


def _history(state: CollabState) -> str:
    return "\n".join(f"[{m.type.upper()}] {m.content[:300]}" for m in state["messages"])


def planner_node(state: CollabState) -> dict:
    t0       = time.perf_counter()
    response = llm.invoke([
        SystemMessage(content=PLANNER_SYS),
        HumanMessage(content=(
            f"Task: {state['original_task']}\nRound: {state['current_round']}/{state['max_rounds']}\n\n"
            f"History:\n{_history(state)}"
        )),
    ])
    ms   = round((time.perf_counter()-t0)*1000, 2)
    span = {"round": state["current_round"], "agent": "planner",
            "output": response.content[:120], "ms": ms}
    return {
        "messages":  [AIMessage(content=f"[PLANNER R{state['current_round']}] {response.content}")],
        "span_log":  state.get("span_log", []) + [span],
    }


def researcher_node(state: CollabState) -> dict:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        "You are a research specialist. Use wikipedia_search and web_search. "
        "Always call at least one tool before answering.",
        f"Task: {state['original_task']}\n\nRound {state['current_round']} history:\n{_history(state)}",
        RESEARCHER_TOOLS,
    )
    ms   = round((time.perf_counter()-t0)*1000, 2)
    span = {"round": state["current_round"], "agent": "researcher",
            "tool_calls": tc_log, "output": output[:120], "ms": ms}
    return {
        "messages": [AIMessage(content=f"[RESEARCHER] {output}")],
        "span_log": state.get("span_log", []) + [span],
    }


def critic_node(state: CollabState) -> dict:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        "You are a critical analyst. Use web_search to find counterarguments, "
        "limitations, and challenges. Be constructive.",
        f"Task: {state['original_task']}\n\nResearch and draft so far:\n{_history(state)}",
        CRITIC_TOOLS,
    )
    ms   = round((time.perf_counter()-t0)*1000, 2)
    span = {"round": state["current_round"], "agent": "critic",
            "tool_calls": tc_log, "output": output[:120], "ms": ms}
    return {
        "messages": [AIMessage(content=f"[CRITIC] {output}")],
        "span_log": state.get("span_log", []) + [span],
    }


def writer_node(state: CollabState) -> dict:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        f"You are a professional writer. Based on the research and critic feedback, "
        f"produce or improve the written document. Always save your output to "
        f"{OUTPUT_FILE} using write_file. If a draft exists, read it first with "
        f"read_file then improve it.",
        (f"Task: {state['original_task']}\nRound {state['current_round']} context:\n"
         f"{_history(state)}\n\nSave your output to {OUTPUT_FILE}"),
        WRITER_TOOLS,
    )
    ms = round((time.perf_counter()-t0)*1000, 2)
    # Read back what was actually saved to disk
    try:
        with open(OUTPUT_FILE, "r") as f:
            saved_draft = f.read()
    except FileNotFoundError:
        saved_draft = output
    span = {"round": state["current_round"], "agent": "writer",
            "tool_calls": tc_log, "revised": bool(state.get("current_draft")),
            "output": output[:120], "ms": ms}
    return {
        "messages":      [AIMessage(content=f"[WRITER] {output}")],
        "current_draft": saved_draft,
        "span_log":      state.get("span_log", []) + [span],
    }


def round_controller_node(state: CollabState) -> dict:
    next_round = state["current_round"] + 1
    done       = next_round > state["max_rounds"]

    if not done:
        t0       = time.perf_counter()
        response = llm.invoke([
            SystemMessage(content=PLANNER_SYS),
            HumanMessage(content=(
                "The writer has finished this round. Review the draft and decide: "
                "continue for another round or stop?\n"
                "Respond ONLY with JSON: {\"continue\": true/false, \"reason\": \"<one sentence>\"}\n\n"
                f"Task: {state['original_task']}\n"
                f"Current draft preview:\n{state.get('current_draft','')[:400]}"
            )),
        ])
        ms = round((time.perf_counter()-t0)*1000, 2)
        try:
            data    = json.loads(response.content.strip().strip("```json").strip("```"))
            do_cont = data.get("continue", False)
            reason  = data.get("reason", "")
        except Exception:
            do_cont = "true" in response.content.lower()
            reason  = response.content.strip()
        done = not do_cont
        span = {"round": state["current_round"], "agent": "planner (end-of-round)",
                "decision": "continue" if do_cont else "STOP", "reason": reason, "ms": ms}
    else:
        span = {"round": state["current_round"], "agent": "round_controller",
                "decision": "STOP (max rounds reached)", "ms": 0}

    return {
        "current_round": next_round,
        "planner_done":  done,
        "span_log":      state.get("span_log", []) + [span],
    }


def should_continue_rounds(state: CollabState) -> str:
    return "END" if state["planner_done"] else "planner_node"


# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH
# ═══════════════════════════════════════════════════════════════

builder = StateGraph(CollabState)
builder.add_node("planner_node",          planner_node)
builder.add_node("researcher_node",       researcher_node)
builder.add_node("critic_node",           critic_node)
builder.add_node("writer_node",           writer_node)
builder.add_node("round_controller_node", round_controller_node)

builder.add_edge(START,                    "planner_node")
builder.add_edge("planner_node",           "researcher_node")
builder.add_edge("researcher_node",        "critic_node")
builder.add_edge("critic_node",            "writer_node")
builder.add_edge("writer_node",            "round_controller_node")
builder.add_conditional_edges(
    "round_controller_node",
    should_continue_rounds,
    {"planner_node": "planner_node", "END": END},
)

graph = builder.compile()
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_15_collaborative",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)

# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════


def run_agent(user_input: str, max_rounds: int = 2) -> dict:
    run_id = str(uuid.uuid4())
    t0     = time.perf_counter()
    final_state = _lookover.invoke(
        graph,
        {
            "messages":      [HumanMessage(content=user_input)],
            "original_task": user_input,
            "current_round": 1,
            "max_rounds":    max_rounds,
            "planner_done":  False,
            "current_draft": "",
            "span_log":      [],
        },
        {"recursion_limit": 40},
    )
    latency_ms = round((time.perf_counter()-t0)*1000, 2)

    span_log  = final_state["span_log"]
    all_tools = [tc for s in span_log for tc in s.get("tool_calls", [])]

    try:
        with open(OUTPUT_FILE, "r") as f:
            final_output = f.read()
    except FileNotFoundError:
        final_output = final_state["current_draft"]

    return {
        "agent":         "agent_15_collaborative",
        "provider":      PROVIDER,
        "model":         getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "run_id":        run_id,
        "input":         user_input,
        "output":        final_output,
        "output_file":   OUTPUT_FILE,
        "rounds_run":    final_state["current_round"] - 1,
        "max_rounds":    max_rounds,
        "span_log":      span_log,
        "total_spans":   len(span_log),
        "tool_calls":    all_tools,
        "message_board": [{"role": m.type, "content": m.content[:200]}
                          for m in final_state["messages"]],
        "latency_ms":    latency_ms,
    }

# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else
        "Research what vector databases are used for in AI systems, "
        "find real-world criticisms of RAG, then write and refine a "
        "balanced 3-paragraph article about RAG in production."
    )
    max_rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    result = run_agent(question, max_rounds=max_rounds)

    print(f"\nProvider      : {result['provider']}  ({result['model']})")
    print(f"Run ID        : {result['run_id']}")
    print(f"Rounds run    : {result['rounds_run']} / {result['max_rounds']}")
    print(f"Output file   : {result['output_file']}")
    print(f"\nReal tool calls ({len(result['tool_calls'])}):")
    for tc in result["tool_calls"]:
        print(f"  [{tc['tool']}]  args={tc['args']}  → {str(tc['output'])[:80]}")
    print(f"\nSpan log:")
    for s in result["span_log"]:
        agent  = s["agent"].ljust(28)
        detail = s.get("reason") or s.get("output", "")
        print(f"  R{s.get('round','?')}  {agent}  {str(detail)[:70]}  [{s.get('ms',0)} ms]")
    print(f"\nFinal draft:\n{result['output'][:800]}")
    print(f"\nLatency : {result['latency_ms']} ms\n")
