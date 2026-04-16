"""
agent_14_parallel.py
---------------------
Phase 1 · Agent 14 — Parallel Agent Execution

Three branches run concurrently via LangGraph's Send API.
Each branch calls real external APIs — no shared module, no mocking.

Branches & their tools:
  researcher : wikipedia_search + web_search
  analyst    : calculator + get_stock_price + get_weather + get_datetime
  critic     : web_search (finds limitations / counterarguments)

Aggregator synthesises all branch outputs and saves to /tmp/agent14_output.txt.

Run:
    python agent_14_parallel.py
    LLM_PROVIDER=vertexai python agent_14_parallel.py
    LLM_PROVIDER=googleai  python agent_14_parallel.py
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
def get_weather(location: str) -> str:
    """
    Get current weather for any city using Open-Meteo API. No API key required.
    Args:
        location: City name, e.g. "Tokyo"
    """
    try:
        with url_request.urlopen(
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={url_parse.quote(location)}&count=1&language=en&format=json", timeout=10
        ) as resp:
            results = json.loads(resp.read()).get("results", [])
        if not results:
            return f"Could not geocode: {location}"
        r = results[0]
        lat, lon = r["latitude"], r["longitude"]
        name, country = r.get("name", location), r.get("country", "")
        with url_request.urlopen(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,"
            f"weather_code,apparent_temperature&timezone=auto", timeout=10
        ) as resp:
            cur = json.loads(resp.read()).get("current", {})
        WMO  = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
                45:"Fog",61:"Slight rain",63:"Moderate rain",80:"Slight showers",95:"Thunderstorm"}
        cond = WMO.get(cur.get("weather_code", 0), f"Code {cur.get('weather_code',0)}")
        return (f"Weather in {name}, {country}: {cond}, "
                f"{cur.get('temperature_2m')}°C (feels {cur.get('apparent_temperature')}°C), "
                f"humidity {cur.get('relative_humidity_2m')}%, wind {cur.get('wind_speed_10m')} km/h. "
                f"Source: Open-Meteo")
    except (url_error.URLError, url_error.HTTPError) as exc:
        raise RuntimeError(f"Open-Meteo error: {exc}") from exc


@tool
def get_stock_price(ticker: str) -> str:
    """
    Get current stock price using Yahoo Finance. Requires: pip install yfinance
    Args:
        ticker: Stock ticker symbol, e.g. "AAPL"
    """
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance not installed. Run: pip install yfinance")
    try:
        info   = yf.Ticker(ticker.upper()).info
        price  = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
        prev   = info.get("previousClose", "N/A")
        name   = info.get("longName", ticker.upper())
        change = round(price - prev, 2) if isinstance(price, (int, float)) and isinstance(prev, (int, float)) else "N/A"
        pct    = round((change / prev) * 100, 2) if isinstance(change, (int, float)) and prev else "N/A"
        return (f"Stock: {name} ({ticker.upper()}) | "
                f"Price: {price} {info.get('currency','USD')} | "
                f"Change: {change} ({pct}%) | Source: Yahoo Finance")
    except Exception as exc:
        raise RuntimeError(f"yfinance error for {ticker}: {exc}") from exc


@tool
def calculator(expression: str) -> str:
    """
    Evaluates a mathematical expression safely.
    Supports: +, -, *, /, **, sqrt(), log(), log10(), sin(), cos(), pi, e, abs(), round().
    Args:
        expression: A Python math expression, e.g. "sqrt(144) + log10(1000)"
    """
    try:
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round})
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
        return f"{expression} = {result}"
    except Exception as exc:
        raise RuntimeError(f"Calculator error for '{expression}': {exc}") from exc


@tool
def get_datetime(timezone_name: str = "UTC") -> str:
    """
    Returns current UTC date/time and the equivalent in the requested timezone.
    Args:
        timezone_name: e.g. "UTC", "IST", "EST", "PST", "JST"
    """
    from datetime import timedelta
    offsets = {"UTC":0,"GMT":0,"IST":5.5,"EST":-5,"EDT":-4,"CST":-6,
               "PST":-8,"PDT":-7,"CET":1,"CEST":2,"JST":9,"AEST":10,"SGT":8}
    now_utc  = datetime.now(timezone.utc)
    offset_h = offsets.get(timezone_name.upper(), 0)
    local_dt = now_utc + timedelta(hours=offset_h)
    sign     = "+" if offset_h >= 0 else ""
    return (f"UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
            f"{timezone_name.upper()}: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} (UTC{sign}{offset_h})")


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
#  BRANCH TOOL GROUPS
# ═══════════════════════════════════════════════════════════════

from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

BRANCH_TOOLS = {
    "researcher": [wikipedia_search, web_search],
    "analyst":    [calculator, get_stock_price, get_weather, get_datetime],
    "critic":     [web_search],
}

BRANCH_SYSTEMS = {
    "researcher": (
        "You are a research specialist. Use wikipedia_search and web_search "
        "to gather accurate facts about the sub-task. Always call at least one tool."
    ),
    "analyst": (
        "You are a data analyst. Use calculator for maths, get_stock_price for market data, "
        "get_weather for weather, get_datetime for current time. Never guess numbers."
    ),
    "critic": (
        "You are a critical analyst. Use web_search to find limitations, risks, "
        "counterarguments, and real-world challenges related to the sub-task."
    ),
}

# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════


class BranchState(TypedDict):
    original_task:  str
    agent_name:     str
    sub_task:       str
    branch_output:  str
    branch_ms:      float
    tool_calls_log: list[dict]


class ParallelState(TypedDict):
    original_task:  str
    sub_tasks:      list[dict]
    branch_results: Annotated[list[dict], lambda a, b: a + b]
    final_output:   str
    run_id:         str
    dispatch_ms:    float


# ═══════════════════════════════════════════════════════════════
#  GRAPH NODES
# ═══════════════════════════════════════════════════════════════

from langgraph.types import Send
from langgraph.graph import StateGraph, START, END


def dispatcher_node(state: ParallelState) -> dict:
    """LLM decomposes the task into exactly 3 parallel sub-tasks."""
    system = (
        "Decompose the following task into exactly 3 parallel sub-tasks:\n"
        "  - researcher : factual background (Wikipedia / web search)\n"
        "  - analyst    : numerical data (calculations, stocks, weather, datetime)\n"
        "  - critic     : limitations, risks, counterarguments (web search)\n\n"
        "Respond ONLY with a JSON array of exactly 3 objects:\n"
        '[{"agent": "researcher", "sub_task": "..."}, '
        '{"agent": "analyst", "sub_task": "..."}, '
        '{"agent": "critic", "sub_task": "..."}]'
    )
    t0       = time.perf_counter()
    response = llm.invoke([SystemMessage(content=system),
                           HumanMessage(content=state["original_task"])])
    ms       = round((time.perf_counter()-t0)*1000, 2)
    try:
        raw       = response.content.strip().strip("```json").strip("```").strip()
        sub_tasks = json.loads(raw)
        if not isinstance(sub_tasks, list) or len(sub_tasks) != 3:
            raise ValueError
    except Exception:
        sub_tasks = [
            {"agent": "researcher", "sub_task": f"Research: {state['original_task']}"},
            {"agent": "analyst",    "sub_task": f"Analyse numerical aspects: {state['original_task']}"},
            {"agent": "critic",     "sub_task": f"Find limitations and risks: {state['original_task']}"},
        ]
    return {"sub_tasks": sub_tasks, "dispatch_ms": ms}


def branch_node(state: BranchState) -> dict:
    """Executes one parallel branch with a real ReAct loop."""
    agent_name = state["agent_name"]
    tools      = BRANCH_TOOLS[agent_name]
    bound_llm  = llm.bind_tools(tools)
    tool_node  = ToolNode(tools)
    tc_log     = []
    messages   = [
        SystemMessage(content=BRANCH_SYSTEMS[agent_name]),
        HumanMessage(content=(
            f"Overall task: {state['original_task']}\n\n"
            f"Your specific sub-task: {state['sub_task']}"
        )),
    ]
    t0 = time.perf_counter()
    for _ in range(5):
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
    return {
        "branch_output":  getattr(messages[-1], "content", "") or "",
        "branch_ms":      round((time.perf_counter()-t0)*1000, 2),
        "tool_calls_log": tc_log,
    }


def aggregator_node(state: ParallelState) -> dict:
    """Fan-in: synthesises all branch results and saves the final answer."""
    branch_context = "\n\n".join(
        f"[{r['agent_name'].upper()} — {r['sub_task'][:60]}]\n{r['branch_output']}"
        for r in state["branch_results"]
    )
    response = llm.invoke([
        SystemMessage(content=(
            "You are a synthesis expert. Integrate the outputs from three parallel "
            "specialist agents (researcher, analyst, critic) into a single, coherent, "
            "well-structured final answer that addresses the original task completely."
        )),
        HumanMessage(content=(
            f"Original task: {state['original_task']}\n\n"
            f"Parallel branch outputs:\n{branch_context}"
        )),
    ])
    final = response.content
    out_path = "/tmp/agent14_output.txt"
    try:
        with open(out_path, "w") as f:
            f.write(final)
    except Exception:
        pass
    return {"final_output": final}


def fan_out(state: ParallelState) -> list[Send]:
    """Spawn one branch_node per sub-task — all run concurrently."""
    return [
        Send("branch_node", {
            "original_task":  state["original_task"],
            "agent_name":     sub["agent"],
            "sub_task":       sub["sub_task"],
            "branch_output":  "",
            "branch_ms":      0.0,
            "tool_calls_log": [],
        })
        for sub in state["sub_tasks"]
    ]


# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH
# ═══════════════════════════════════════════════════════════════

builder = StateGraph(ParallelState)
builder.add_node("dispatcher_node", dispatcher_node)
builder.add_node("branch_node",     branch_node)
builder.add_node("aggregator_node", aggregator_node)

builder.add_edge(START, "dispatcher_node")
builder.add_conditional_edges("dispatcher_node", fan_out, ["branch_node"])
builder.add_edge("branch_node",     "aggregator_node")
builder.add_edge("aggregator_node", END)

graph = builder.compile()
from lookover_codex_sdk.langgraph import LookoverLangGraphListener

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_14_parallel",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
)

# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════


def run_agent(user_input: str) -> dict:
    run_id = str(uuid.uuid4())
    t0     = time.perf_counter()
    final_state = _lookover.invoke(
        graph,
        {
            "original_task":  user_input,
            "sub_tasks":      [],
            "branch_results": [],
            "final_output":   "",
            "run_id":         run_id,
            "dispatch_ms":    0.0,
        },
    )
    latency_ms     = round((time.perf_counter()-t0)*1000, 2)
    branch_results = final_state.get("branch_results", [])
    all_tool_calls = [tc for r in branch_results for tc in r.get("tool_calls_log", [])]
    return {
        "agent":          "agent_14_parallel",
        "provider":       PROVIDER,
        "model":          getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "run_id":         run_id,
        "input":          user_input,
        "output":         final_state["final_output"],
        "sub_tasks":      final_state["sub_tasks"],
        "branch_results": branch_results,
        "num_branches":   len(branch_results),
        "dispatch_ms":    final_state["dispatch_ms"],
        "branch_ms_each": {r["agent_name"]: r["branch_ms"] for r in branch_results},
        "tool_calls":     all_tool_calls,
        "latency_ms":     latency_ms,
    }

# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else
        "What is the current weather in Paris, the AAPL stock price, "
        "and what are the main benefits and risks of AI agents in finance?"
    )
    result = run_agent(question)
    print(f"\nProvider      : {result['provider']}  ({result['model']})")
    print(f"Run ID        : {result['run_id']}")
    print(f"Dispatch time : {result['dispatch_ms']} ms")
    print(f"Branches      : {result['num_branches']}")
    print(f"\nSub-tasks dispatched:")
    for st in result["sub_tasks"]:
        print(f"  [{st['agent'].ljust(12)}] {st['sub_task'][:80]}")
    print(f"\nBranch latencies (ran concurrently):")
    for agent, ms in result["branch_ms_each"].items():
        print(f"  {agent.ljust(12)} : {ms} ms")
    print(f"\nReal tool calls ({len(result['tool_calls'])}):")
    for tc in result["tool_calls"]:
        print(f"  [{tc['tool']}]  args={tc['args']}  → {str(tc['output'])[:80]}")
    print(f"\nTotal wall-clock : {result['latency_ms']} ms")
    print(f"\nOutput:\n{result['output'][:600]}\n")
