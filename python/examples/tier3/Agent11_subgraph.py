"""
agent_11_subgraph.py
---------------------
Phase 1 · Agent 11 — Agent with Subgraph

A parent graph delegates a specialised task to a compiled child subgraph
(treated as a single node from the parent's perspective).

Architecture:
  Parent graph
  ├── router_node      : LLM decides whether the query needs research or is simple
  ├── research_subgraph: Child StateGraph that does multi-step research + summarise
  │     ├── gather_node   : simulates fetching information from multiple sources
  │     └── summarise_node: LLM summarises the gathered information
  └── direct_node      : LLM answers simple queries directly (no subgraph)

What your audit SDK should capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ✔ Parent node transitions
  ✔ SUBGRAPH ENTRY event  — parent handed off to child
  ✔ Child node transitions (inside the subgraph)
  ✔ SUBGRAPH EXIT event   — child returned result to parent
  ✔ Parent/child span correlation (shared thread_id, different graph names)
  ✔ Which execution path was taken (research vs direct)
  ✔ Sources gathered inside the subgraph

Run:
    python agent_11_subgraph.py
    LLM_PROVIDER=vertexai python agent_11_subgraph.py
    LLM_PROVIDER=googleai  python agent_11_subgraph.py
"""

import os
import time
import sys
from typing import Annotated, TypedDict
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
#  SHARED STATE SCHEMAS
# ═══════════════════════════════════════════════════════════════

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages


class SubgraphState(TypedDict):
    """State used INSIDE the research subgraph."""
    query:           str
    gathered_sources: list[dict]   # [{source, content}]
    summary:         str


class ParentState(TypedDict):
    """State used by the parent graph."""
    messages:    Annotated[list[AnyMessage], add_messages]
    query:       str
    route:       str             # "research" | "direct"
    subgraph_summary: str        # filled in by the subgraph
    final_answer: str


# ═══════════════════════════════════════════════════════════════
#  RESEARCH SUBGRAPH
# ═══════════════════════════════════════════════════════════════

import os as _os
from pathlib import Path
from langgraph.graph import StateGraph, START, END

# ── Load knowledge base from docs/ directory beside this file ───────────────
_DOCS_DIR = Path(_os.path.dirname(_os.path.abspath(__file__))) / "docs"

print(f"[Subgraph] Loading knowledge base from {_DOCS_DIR} …")
KNOWLEDGE_BASE: dict[str, str] = {}
for _path in sorted(_DOCS_DIR.glob("*.txt")):
    KNOWLEDGE_BASE[_path.stem] = _path.read_text(encoding="utf-8").strip()
print(f"[Subgraph] Loaded {len(KNOWLEDGE_BASE)} documents: {list(KNOWLEDGE_BASE.keys())}")


def gather_node(state: SubgraphState) -> dict:
    """
    Simulates fetching relevant information from multiple sources.
    In production: replace with real API calls, DB queries, or retrieval chains.
    """
    query_lower = state["query"].lower()
    gathered    = []

    for keyword, content in KNOWLEDGE_BASE.items():
        if keyword in query_lower or any(w in query_lower for w in keyword.split()):
            gathered.append({"source": f"{keyword}_kb", "content": content})

    # Fallback: return all sources if none matched
    if not gathered:
        gathered = [{"source": k + "_kb", "content": v} for k, v in KNOWLEDGE_BASE.items()]

    return {"gathered_sources": gathered}


def summarise_node(state: SubgraphState) -> dict:
    """LLM summarises the gathered sources into a concise answer."""
    context = "\n\n".join(
        f"[{s['source']}] {s['content']}" for s in state["gathered_sources"]
    )
    prompt_msgs = [
        SystemMessage(content=(
            "You are a research summariser. Given the sources below, write a concise, "
            "accurate answer to the query. Cite source names in your answer."
        )),
        HumanMessage(content=f"Query: {state['query']}\n\nSources:\n{context}"),
    ]
    response = llm.invoke(prompt_msgs)
    return {"summary": response.content}


# ── Compile the subgraph ─────────────────────────────────────────────────────
sub_builder = StateGraph(SubgraphState)
sub_builder.add_node("gather_node",    gather_node)
sub_builder.add_node("summarise_node", summarise_node)
sub_builder.add_edge(START,            "gather_node")
sub_builder.add_edge("gather_node",    "summarise_node")
sub_builder.add_edge("summarise_node", END)

research_subgraph = sub_builder.compile()


# ═══════════════════════════════════════════════════════════════
#  PARENT GRAPH NODES
# ═══════════════════════════════════════════════════════════════

def router_node(state: ParentState) -> dict:
    """
    LLM decides if the query needs deep research (subgraph) or a direct answer.
    Returns route='research' or route='direct'.
    """
    prompt_msgs = [
        SystemMessage(content=(
            "You are a query router. Classify the user's query:\n"
            "  - 'research' if it asks about technical concepts, requires explanation, "
            "    or needs information synthesis from multiple sources.\n"
            "  - 'direct'   if it is a simple greeting, small talk, or trivial factual question.\n"
            "Reply with ONLY one word: research OR direct."
        )),
        HumanMessage(content=state["query"]),
    ]
    response = llm.invoke(prompt_msgs)
    route    = "research" if "research" in response.content.lower() else "direct"
    return {"route": route}


def research_node(state: ParentState) -> dict:
    """
    Delegates to the research subgraph.
    Maps ParentState fields → SubgraphState, runs the subgraph, maps result back.
    """
    sub_input  = {"query": state["query"], "gathered_sources": [], "summary": ""}
    sub_output = research_subgraph.invoke(sub_input)
    return {
        "subgraph_summary": sub_output["summary"],
        "final_answer":     sub_output["summary"],
    }


def direct_node(state: ParentState) -> dict:
    """Answers simple queries directly without invoking the subgraph."""
    prompt_msgs = [
        SystemMessage(content="You are a helpful, concise assistant."),
        HumanMessage(content=state["query"]),
    ]
    response = llm.invoke(prompt_msgs)
    return {"final_answer": response.content}


def route_decision(state: ParentState) -> str:
    return state["route"]  # "research" or "direct"


# ── Compile the parent graph ─────────────────────────────────────────────────
parent_builder = StateGraph(ParentState)
parent_builder.add_node("router_node",   router_node)
parent_builder.add_node("research_node", research_node)
parent_builder.add_node("direct_node",   direct_node)

parent_builder.add_edge(START, "router_node")
parent_builder.add_conditional_edges(
    "router_node",
    route_decision,
    {"research": "research_node", "direct": "direct_node"},
)
parent_builder.add_edge("research_node", END)
parent_builder.add_edge("direct_node",   END)

parent_graph = parent_builder.compile()
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_11_subgraph",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

def run_agent(user_input: str) -> dict:
    initial_state: ParentState = {
        "messages":        [HumanMessage(content=user_input)],
        "query":           user_input,
        "route":           "",
        "subgraph_summary": "",
        "final_answer":    "",
    }

    # Track node transitions in the parent graph for audit logging
    parent_transitions = []
    subgraph_entered   = False

    t0 = time.perf_counter()

    for step in parent_graph.stream(initial_state, stream_mode="updates"):
        for node_name, state_update in step.items():
            parent_transitions.append({
                "node":        node_name,
                "route":       state_update.get("route", ""),
                "has_summary": bool(state_update.get("subgraph_summary")),
            })
            if node_name == "research_node":
                subgraph_entered = True

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Get the final state
    final_state = _lookover.invoke(parent_graph, initial_state)

    # If research path was taken, also stream the subgraph internals for logging
    subgraph_transitions = []
    gathered_sources     = []
    if subgraph_entered:
        sub_input = {"query": user_input, "gathered_sources": [], "summary": ""}
        for step in research_subgraph.stream(sub_input, stream_mode="updates"):
            for node_name, sub_update in step.items():
                subgraph_transitions.append({"node": node_name})
                if node_name == "gather_node":
                    gathered_sources = sub_update.get("gathered_sources", [])

    return {
        "agent":                 "agent_11_subgraph",
        "provider":              PROVIDER,
        "model":                 getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":                 user_input,
        "output":                final_state["final_answer"],
        "route":                 final_state["route"],
        "subgraph_entered":      subgraph_entered,
        "parent_transitions":    parent_transitions,
        "subgraph_transitions":  subgraph_transitions,   # child node trace
        "gathered_sources":      [s["source"] for s in gathered_sources],
        "latency_ms":            latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    queries = [
        sys.argv[1] if len(sys.argv) > 1 else "Explain how LangGraph subgraphs work and why they are useful for audit logging.",
        "Hello, how are you?",   # Should take the "direct" route
    ]

    for query in queries:
        result = run_agent(query)

        print(f"\n{'═' * 60}")
        print(f"  Provider  : {result['provider']}  ({result['model']})")
        print(f"  Input     : {result['input']}")
        print(f"  Route     : {result['route'].upper()}")
        print(f"\n  Parent transitions  : {[t['node'] for t in result['parent_transitions']]}")
        if result["subgraph_entered"]:
            print(f"  Subgraph transitions: {[t['node'] for t in result['subgraph_transitions']]}")
            print(f"  Sources gathered    : {result['gathered_sources']}")
        print(f"\n  Output    : {result['output'][:300]}{'…' if len(result['output']) > 300 else ''}")
        print(f"  Latency   : {result['latency_ms']} ms")
    print()
