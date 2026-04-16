"""
agent_13_hierarchical.py
--------------------------
Phase 1 · Agent 13 — Hierarchical Agent Team (3-level hierarchy)

Level 1 — Top Supervisor   : decomposes task, delegates to sub-supervisors
Level 2 — research_supervisor | content_supervisor
Level 3 — fact_finder (wikipedia + web), data_analyst (calculator + stocks + weather),
           writer (write_file), editor (read_file + write_file)

All tool calls are real — no shared module, no mocking.

Real external calls:
  ✔ Wikipedia MediaWiki REST API
  ✔ DuckDuckGo Instant Answer API
  ✔ Open-Meteo weather API
  ✔ Yahoo Finance via yfinance
  ✔ Local file read/write

Run:
    python agent_13_hierarchical.py
    LLM_PROVIDER=vertexai python agent_13_hierarchical.py
    LLM_PROVIDER=googleai  python agent_13_hierarchical.py
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

from lookover_codex_sdk.langchain import LookoverCallbackHandler

_lookover = LookoverCallbackHandler(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_13_hierarchical",
    agent_version="1.0.0",
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
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
        WMO  = {0:"Clear sky", 1:"Mainly clear", 2:"Partly cloudy", 3:"Overcast",
                45:"Fog", 61:"Slight rain", 63:"Moderate rain",
                80:"Slight showers", 95:"Thunderstorm"}
        cond = WMO.get(cur.get("weather_code", 0), f"Code {cur.get('weather_code', 0)}")
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
                f"Change: {change} ({pct}%) | "
                f"Market cap: {info.get('marketCap','N/A')} | Source: Yahoo Finance")
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
#  TOOL GROUPS PER WORKER
# ═══════════════════════════════════════════════════════════════

from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

FACT_FINDER_TOOLS = [wikipedia_search, web_search]
ANALYST_TOOLS     = [calculator, get_stock_price, get_weather, get_datetime]
WRITER_TOOLS      = [write_file]
EDITOR_TOOLS      = [read_file, write_file]
OUTPUT_FILE       = "/tmp/agent13_output.txt"

# ═══════════════════════════════════════════════════════════════
#  HELPERS
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
                           "output": getattr(tm, "content", "")[:400]})
    return getattr(messages[-1], "content", "") or "", tc_log


def parse_json_decision(text: str, choices: list[str], fallback: str) -> tuple[str, str]:
    try:
        data   = json.loads(text.strip().strip("```json").strip("```").strip())
        next_a = data.get("next", fallback)
        reason = data.get("reason", "")
    except Exception:
        next_a = next((c for c in choices if c in text.lower()), fallback)
        reason = text.strip()
    return (next_a if next_a in choices else fallback), reason


# ═══════════════════════════════════════════════════════════════
#  LEVEL 3 — WORKERS
# ═══════════════════════════════════════════════════════════════

def run_fact_finder(task: str, span_log: list) -> str:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        "You are a fact-finding specialist. Use wikipedia_search and web_search. "
        "Always call at least one tool.", task, FACT_FINDER_TOOLS)
    span_log.append({"level":3,"agent":"fact_finder","task":task[:80],
                     "tool_calls":tc_log,"output":output[:120],
                     "ms":round((time.perf_counter()-t0)*1000,2)})
    return output


def run_data_analyst(task: str, span_log: list) -> str:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        "You are a data analyst. Use calculator, get_stock_price, get_weather, get_datetime. "
        "Never guess numbers.", task, ANALYST_TOOLS)
    span_log.append({"level":3,"agent":"data_analyst","task":task[:80],
                     "tool_calls":tc_log,"output":output[:120],
                     "ms":round((time.perf_counter()-t0)*1000,2)})
    return output


def run_writer(task: str, span_log: list) -> str:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        f"You are a professional writer. Compose a clear document and save it "
        f"to {OUTPUT_FILE} using write_file.",
        f"{task}\n\nSave the final document to {OUTPUT_FILE} using write_file.",
        WRITER_TOOLS)
    span_log.append({"level":3,"agent":"writer","task":task[:80],
                     "tool_calls":tc_log,"output":output[:120],
                     "ms":round((time.perf_counter()-t0)*1000,2)})
    return output


def run_editor(task: str, span_log: list) -> str:
    t0 = time.perf_counter()
    output, tc_log = react_loop(
        "You are a professional editor. Read the existing draft with read_file, "
        "improve it for clarity and conciseness, then overwrite with write_file.",
        f"{task}\n\nFirst read {OUTPUT_FILE} with read_file, then improve and overwrite it.",
        EDITOR_TOOLS)
    span_log.append({"level":3,"agent":"editor","task":task[:80],
                     "tool_calls":tc_log,"output":output[:120],
                     "ms":round((time.perf_counter()-t0)*1000,2)})
    return output


# ═══════════════════════════════════════════════════════════════
#  LEVEL 2 — SUB-SUPERVISORS
# ═══════════════════════════════════════════════════════════════

RESEARCH_SUP_SYS = ('''You are the Research Sub-Supervisor managing two workers:
  - fact_finder  : searches Wikipedia and the web
  - data_analyst : calculations, stock prices, weather, datetime
Decide which worker next, or END when research is complete.
Respond ONLY with JSON: {"next": "<fact_finder|data_analyst|END>", "reason": "<one sentence>"}''')

CONTENT_SUP_SYS = ('''You are the Content Sub-Supervisor managing two workers:
  - writer : drafts and saves the document to disk
  - editor : reads saved draft, improves it, overwrites
Decide which worker next, or END when content is polished.
Respond ONLY with JSON: {"next": "<writer|editor|END>", "reason": "<one sentence>"}''')


def run_research_supervisor(task: str, span_log: list) -> str:
    conversation = task
    outputs      = []
    for _ in range(4):
        t0       = time.perf_counter()
        response = llm.invoke(
            [SystemMessage(content=RESEARCH_SUP_SYS), HumanMessage(content=conversation)],
            config={"callbacks": [_lookover]},
        )
        ms       = round((time.perf_counter()-t0)*1000, 2)
        next_w, reason = parse_json_decision(response.content, ["fact_finder","data_analyst","END"], "END")
        span_log.append({"level":2,"agent":"research_supervisor",
                         "routed_to":next_w,"reason":reason,"ms":ms})
        if next_w == "END":
            break
        worker_out = (run_fact_finder if next_w=="fact_finder" else run_data_analyst)(conversation, span_log)
        outputs.append(f"[{next_w}]: {worker_out}")
        conversation = task + "\n\nFindings so far:\n" + "\n".join(outputs)
    return "\n".join(outputs) or "No research output."


def run_content_supervisor(task: str, research: str, span_log: list) -> str:
    context = f"Original task: {task}\n\nResearch findings:\n{research}"
    for _ in range(4):
        t0       = time.perf_counter()
        response = llm.invoke(
            [SystemMessage(content=CONTENT_SUP_SYS), HumanMessage(content=context)],
            config={"callbacks": [_lookover]},
        )
        ms       = round((time.perf_counter()-t0)*1000, 2)
        next_w, reason = parse_json_decision(response.content, ["writer","editor","END"], "END")
        span_log.append({"level":2,"agent":"content_supervisor",
                         "routed_to":next_w,"reason":reason,"ms":ms})
        if next_w == "END":
            break
        (run_writer if next_w=="writer" else run_editor)(context, span_log)
    try:
        with open(OUTPUT_FILE, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "No output file produced."


# ═══════════════════════════════════════════════════════════════
#  LEVEL 1 — TOP SUPERVISOR
# ═══════════════════════════════════════════════════════════════

TOP_SUP_SYS = ('''You are the Top-Level Supervisor coordinating two sub-teams:
  - research_supervisor : fact-finding, data analysis, knowledge retrieval
  - content_supervisor  : writing and editing
Respond ONLY with JSON:
{"next": "<research_supervisor|content_supervisor|END>", "reason": "<one sentence>"}''')


def run_agent(user_input: str) -> dict:
    run_id:    str       = str(uuid.uuid4())
    span_log: list[dict] = []
    context              = ""
    research_findings    = ""
    final_content        = ""

    t0 = time.perf_counter()
    for _ in range(6):
        t1       = time.perf_counter()
        response = llm.invoke(
            [SystemMessage(content=TOP_SUP_SYS), HumanMessage(content=f"Task: {user_input}\n\nContext:\n{context}")],
            config={"callbacks": [_lookover]},
        )
        ms       = round((time.perf_counter()-t1)*1000, 2)
        next_s, reason = parse_json_decision(
            response.content, ["research_supervisor","content_supervisor","END"], "END"
        )
        span_log.append({"level":1,"agent":"top_supervisor","routed_to":next_s,"reason":reason,"ms":ms})
        if next_s == "END":
            break
        if next_s == "research_supervisor":
            research_findings = run_research_supervisor(user_input, span_log)
            context += f"\n\n[Research done]:\n{research_findings[:400]}"
        elif next_s == "content_supervisor":
            final_content = run_content_supervisor(user_input, research_findings, span_log)
            context += f"\n\n[Content done]:\n{final_content[:400]}"

    latency_ms   = round((time.perf_counter()-t0)*1000, 2)
    final_output = final_content or research_findings or "No output produced."
    all_tool_calls = [tc for s in span_log for tc in s.get("tool_calls", [])]

    return {
        "agent":          "agent_13_hierarchical",
        "provider":       PROVIDER,
        "model":          getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "run_id":         run_id,
        "input":          user_input,
        "output":         final_output,
        "output_file":    OUTPUT_FILE,
        "span_log":       span_log,
        "total_spans":    len(span_log),
        "level_summary":  {1:[s["agent"] for s in span_log if s["level"]==1],
                           2:[s["agent"] for s in span_log if s["level"]==2],
                           3:[s["agent"] for s in span_log if s["level"]==3]},
        "agents_invoked": list({s["agent"] for s in span_log}),
        "tool_calls":     all_tool_calls,
        "latency_ms":     latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else
        "Search Wikipedia for 'retrieval-augmented generation', get the MSFT stock price, "
        "calculate log(1000000), then write and edit a concise article covering all findings."
    )
    result = run_agent(question)
    print(f"\nProvider       : {result['provider']}  ({result['model']})")
    print(f"Run ID         : {result['run_id']}")
    print(f"Agents invoked : {result['agents_invoked']}")
    print(f"Total spans    : {result['total_spans']}")
    print(f"Output file    : {result['output_file']}")
    print(f"\nSpan log (3-level hierarchy):")
    for span in result["span_log"]:
        indent = "  " * span["level"]
        label  = span["agent"].ljust(22)
        if "routed_to" in span:
            detail = f"→ {span['routed_to']}  |  {span.get('reason','')[:55]}"
        else:
            tcs    = span.get("tool_calls", [])
            detail = f"tools={[tc['tool'] for tc in tcs]}  {span.get('output','')[:40]}"
        print(f"{indent}L{span['level']} {label}  {detail}  [{span['ms']} ms]")
    print(f"\nOutput (first 600 chars):\n{result['output'][:600]}")
    print(f"\nLatency : {result['latency_ms']} ms\n")
