"""
agent_12_supervisor.py
-----------------------
Phase 1 · Agent 12 — Supervisor Multi-Agent

A supervisor LLM routes tasks to specialised worker agents.
Workers carry their own real tools — no shared module, no mocking.

Workers & their tools:
  researcher : wikipedia_search + web_search
  analyst    : calculator + get_stock_price + get_weather + get_datetime
  writer     : write_file  (persists final answer to /tmp/agent12_output.txt)

Run:
    python agent_12_supervisor.py
    LLM_PROVIDER=vertexai python agent_12_supervisor.py
    LLM_PROVIDER=googleai  python agent_12_supervisor.py
"""

import os
import sys
import time
import uuid
import json
import math
from datetime import datetime, timezone
from urllib import request as url_request, parse as url_parse, error as url_error
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LOOKOVER SDK
# ═══════════════════════════════════════════════════════════════

_sdk_path = os.getenv("LOOKOVER_SDK_PATH", "")
if _sdk_path and _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)

_sdk_backend = os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080").rstrip("/")
_prefer_reference_sdk = _sdk_backend.endswith(":8081")

if _prefer_reference_sdk:
    try:
        from lookover_sdk.langgraph import LookoverLangGraphListener  # type: ignore[import-not-found] # noqa: E402
    except ImportError:
        from lookover_codex_sdk.langgraph import LookoverLangGraphListener  # noqa: E402
else:
    from lookover_codex_sdk.langgraph import LookoverLangGraphListener  # noqa: E402

# ═══════════════════════════════════════════════════════════════
#  LLM SETUP
# ═══════════════════════════════════════════════════════════════

PROVIDER = os.getenv("LLM_PROVIDER", "vertexai").lower()

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
        model_name=os.getenv("VERTEXAI_MODEL", "gemini-2.5-flash-lite"),
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

_lookover = LookoverLangGraphListener(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_12_supervisor",
    agent_version="1.0.0",
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
    base_url=_sdk_backend,
)

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
    _ua = {"User-Agent": "AuditSDK-Agent/1.0 (lookover-audit-bot)"}
    try:
        req = url_request.Request(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={url_parse.quote(query)}&srlimit=1&format=json",
            headers=_ua,
        )
        with url_request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read()).get("query", {}).get("search", [])
        if not results:
            return f"No Wikipedia article found for: {query}"
        title = results[0]["title"]
        req2 = url_request.Request(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{url_parse.quote(title)}",
            headers=_ua,
        )
        with url_request.urlopen(req2, timeout=10) as resp:
            page = json.loads(resp.read())
        url = page.get("content_urls", {}).get("desktop", {}).get("page", "")
        return f"[Wikipedia: {title}]\n{page.get('extract','No extract.')}\nSource: {url}"
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
            return f"{abstract}\nSource: {data.get('AbstractURL','')}"
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
            f"https://geocoding-api.open-meteo.com/v1/search?name={url_parse.quote(location)}&count=1&language=en&format=json",
            timeout=10,
        ) as resp:
            results = json.loads(resp.read()).get("results", [])
        if not results:
            return f"Could not geocode: {location}"
        r = results[0]
        lat, lon, name, country = r["latitude"], r["longitude"], r.get("name", location), r.get("country", "")
        with url_request.urlopen(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,apparent_temperature&timezone=auto",
            timeout=10,
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
        change = round(price - prev, 2) if isinstance(price, (int,float)) and isinstance(prev, (int,float)) else "N/A"
        pct    = round((change / prev) * 100, 2) if isinstance(change, (int,float)) and prev else "N/A"
        return (f"Stock: {name} ({ticker.upper()}) | Price: {price} {info.get('currency','USD')} | "
                f"Change: {change} ({pct}%) | Market cap: {info.get('marketCap','N/A')} | Source: Yahoo Finance")
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
#  TOOL GROUPS PER WORKER
# ═══════════════════════════════════════════════════════════════

RESEARCHER_TOOLS = [wikipedia_search, web_search]
ANALYST_TOOLS    = [calculator, get_stock_price, get_weather, get_datetime]
WRITER_TOOLS     = [write_file]
OUTPUT_FILE      = "/tmp/agent12_output.txt"

# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════

from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

WORKERS = ["researcher", "analyst", "writer"]


class SupervisorState(TypedDict):
    messages:    Annotated[list[AnyMessage], add_messages]
    next_worker: str
    hop_log:     list[dict]
    run_id:      str


# ═══════════════════════════════════════════════════════════════
#  SUPERVISOR NODE
# ═══════════════════════════════════════════════════════════════

SUPERVISOR_SYSTEM = """You are a task supervisor managing three specialist workers:
  - researcher : searches Wikipedia and the web for factual information
  - analyst    : runs calculations, fetches stock prices, checks weather, gets datetime
  - writer     : writes the final polished answer to a file

Decide which worker should act next, or END when the task is fully complete.
Respond with ONLY valid JSON: {"next": "<researcher|analyst|writer|END>", "reason": "<one sentence>"}
"""


def supervisor_node(state: SupervisorState) -> dict:
    response = llm.invoke([SystemMessage(content=SUPERVISOR_SYSTEM)] + state["messages"])
    raw = response.content
    if isinstance(raw, list):
        raw = " ".join(p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in raw)
    try:
        decision = json.loads(raw.strip().strip("```json").strip("```").strip())
        next_w, reason = decision.get("next", "END"), decision.get("reason", "")
    except Exception:
        content = raw.lower()
        next_w  = next((w for w in WORKERS if w in content), "END")
        reason  = raw.strip()
    if next_w not in WORKERS:
        next_w = "END"
    hop = {"from": "supervisor", "to": next_w, "reason": reason,
           "step": len(state.get("hop_log", [])) + 1}
    return {
        "next_worker": next_w,
        "hop_log":     state.get("hop_log", []) + [hop],
        "messages":    [AIMessage(content=f"[Supervisor → {next_w}]: {reason}")],
    }


# ═══════════════════════════════════════════════════════════════
#  WORKER NODES  (real ReAct loop per worker)
# ═══════════════════════════════════════════════════════════════

WORKER_SYSTEMS = {
    "researcher": (
        "You are a research specialist. Use wikipedia_search and web_search to find "
        "accurate, up-to-date information. Always call at least one search tool before answering."
    ),
    "analyst": (
        "You are a data analyst. Use calculator for maths, get_stock_price for market data, "
        "get_weather for weather, get_datetime for current time. Never guess numbers."
    ),
    "writer": (
        f"You are a professional writer. Compose the final polished answer based on all "
        f"prior research and analysis. Save it to {OUTPUT_FILE} using write_file."
    ),
}

WORKER_TOOL_NODES = {
    "researcher": ToolNode(RESEARCHER_TOOLS),
    "analyst":    ToolNode(ANALYST_TOOLS),
    "writer":     ToolNode(WRITER_TOOLS),
}

WORKER_LLMS = {
    "researcher": llm.bind_tools(RESEARCHER_TOOLS),
    "analyst":    llm.bind_tools(ANALYST_TOOLS),
    "writer":     llm.bind_tools(WRITER_TOOLS),
}


def make_worker_node(worker_name: str):
    def worker_node(state: SupervisorState) -> dict:
        sys_msg    = SystemMessage(content=WORKER_SYSTEMS[worker_name])
        bound_llm  = WORKER_LLMS[worker_name]
        tool_node  = WORKER_TOOL_NODES[worker_name]
        tc_log     = []
        messages   = list(state["messages"])

        for _ in range(6):
            response = bound_llm.invoke([sys_msg] + messages)
            messages.append(response)
            if not getattr(response, "tool_calls", None):
                break
            tool_results = tool_node.invoke({"messages": [response]})
            for tm in tool_results.get("messages", []):
                messages.append(tm)
                tc_id   = getattr(tm, "tool_call_id", None)
                matched = next((tc for tc in response.tool_calls if tc["id"] == tc_id), {})
                tc_log.append({"tool": matched.get("name","?"), "args": matched.get("args",{}),
                                "output": getattr(tm,"content","")[:300]})

        final = getattr(messages[-1], "content", "") or ""
        if isinstance(final, list):
            final = " ".join(p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in final)
        hop   = {"from": worker_name, "to": "supervisor", "tool_calls": tc_log,
                 "output": final[:120] + ("…" if len(final)>120 else ""),
                 "step": len(state.get("hop_log",[])) + 1}
        return {
            "messages": [AIMessage(content=f"[{worker_name.capitalize()}]: {final}")],
            "hop_log":  state.get("hop_log", []) + [hop],
        }

    worker_node.__name__ = f"{worker_name}_node"
    return worker_node


researcher_node = make_worker_node("researcher")
analyst_node    = make_worker_node("analyst")
writer_node     = make_worker_node("writer")

# ═══════════════════════════════════════════════════════════════
#  BUILD GRAPH
# ═══════════════════════════════════════════════════════════════

from langgraph.graph import StateGraph, START, END as GRAPH_END


def route_to_worker(state: SupervisorState) -> str:
    return state["next_worker"]


builder = StateGraph(SupervisorState)
builder.add_node("supervisor",  supervisor_node)
builder.add_node("researcher",  researcher_node)
builder.add_node("analyst",     analyst_node)
builder.add_node("writer",      writer_node)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor", route_to_worker,
    {"researcher":"researcher","analyst":"analyst","writer":"writer","END":GRAPH_END},
)
for w in WORKERS:
    builder.add_edge(w, "supervisor")

graph = builder.compile()

# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════


def run_agent(user_input: str) -> dict:
    run_id = str(uuid.uuid4())
    t0     = time.perf_counter()
    final_state = _lookover.invoke(
        graph,
        {"messages": [HumanMessage(content=user_input)], "next_worker": "",
         "hop_log": [], "run_id": run_id},
        {"recursion_limit": 20},
    )
    latency_ms = round((time.perf_counter()-t0)*1000, 2)

    final_answer = ""
    for msg in reversed(final_state["messages"]):
        content = getattr(msg, "content", "")
        if isinstance(msg, AIMessage) and content and not content.startswith("[Supervisor"):
            final_answer = content
            break

    hop_log   = final_state["hop_log"]
    all_tools = [tc for h in hop_log for tc in h.get("tool_calls", [])]
    return {
        "agent":        "agent_12_supervisor",
        "provider":     PROVIDER,
        "model":        getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "run_id":       run_id,
        "input":        user_input,
        "output":       final_answer,
        "output_file":  OUTPUT_FILE,
        "hop_log":      hop_log,
        "total_hops":   len(hop_log),
        "workers_used": list({h["from"] for h in hop_log if h["from"] in WORKERS}),
        "tool_calls":   all_tools,
        "latency_ms":   latency_ms,
    }

# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else
        "Search Wikipedia for LangGraph, get the current weather in London, "
        "calculate sqrt(98596), then write a concise summary of all findings."
    )
    result = run_agent(question)
    print(f"\nProvider     : {result['provider']}  ({result['model']})")
    print(f"Run ID       : {result['run_id']}")
    print(f"Workers used : {result['workers_used']}")
    print(f"Total hops   : {result['total_hops']}")
    print(f"\nReal tool calls ({len(result['tool_calls'])}):")
    for tc in result["tool_calls"]:
        print(f"  [{tc['tool']}]  args={tc['args']}  → {str(tc['output'])[:80]}")
    print(f"\nHop log:")
    for hop in result["hop_log"]:
        detail = hop.get("reason") or hop.get("output","")
        print(f"  step {hop['step']:02d}  {hop['from'].ljust(12)} → {hop.get('to','—').ljust(12)}  |  {str(detail)[:70]}")
    print(f"\nOutput  : {result['output'][:400]}")
    print(f"Latency : {result['latency_ms']} ms\n")
