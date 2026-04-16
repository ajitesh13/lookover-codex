"""
agent_05_multi_tool.py
-----------------------
Phase 1 · Agent 5 — Multi-Tool Agent

Agent with 4 tools: calculator, get_current_datetime, word_counter, and
unit_converter. The LLM picks the right tool(s) for each query — sometimes
chaining multiple tool calls in a single run.

Run:
    python agent_05_multi_tool.py
    LLM_PROVIDER=vertexai python agent_05_multi_tool.py
    LLM_PROVIDER=googleai python agent_05_multi_tool.py
"""

import os
import time
import sys
import math
from datetime import datetime, timezone
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
#  TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════

from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluates a mathematical expression and returns the result.
    Supports: +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e.

    Args:
        expression: A valid Python math expression, e.g. "sqrt(144) + 2**8"
    """
    try:
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round})
        return str(eval(expression, {"__builtins__": {}}, allowed))  # noqa: S307
    except Exception as exc:
        return f"Error: {exc}"


@tool
def get_current_datetime(timezone_name: str = "UTC") -> str:
    """
    Returns the current date and time.

    Args:
        timezone_name: Timezone label to include in the response (informational only).
                       Actual time is always returned in UTC.
    """
    now = datetime.now(timezone.utc)
    return f"Current UTC datetime: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (requested tz label: {timezone_name})"


@tool
def word_counter(text: str) -> str:
    """
    Counts words, characters, and sentences in a given text.

    Args:
        text: The text to analyse.
    """
    words      = len(text.split())
    chars      = len(text)
    chars_nows = len(text.replace(" ", ""))
    sentences  = text.count(".") + text.count("!") + text.count("?")
    return (
        f"Words: {words} | Characters (with spaces): {chars} | "
        f"Characters (no spaces): {chars_nows} | Sentences: {sentences}"
    )


@tool
def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    """
    Converts a value between common units. Supports:
      Length : meters, kilometers, miles, feet, inches, centimeters
      Weight : kilograms, grams, pounds, ounces
      Temp   : celsius, fahrenheit, kelvin

    Args:
        value:     The numeric value to convert.
        from_unit: Source unit (e.g. "kilometers").
        to_unit:   Target unit (e.g. "miles").
    """
    f, t = from_unit.lower().strip(), to_unit.lower().strip()

    # ── Length (base: meters) ────────────────────────────────
    to_meters   = {"meters": 1, "kilometres": 1000, "kilometers": 1000,
                   "miles": 1609.344, "feet": 0.3048, "inches": 0.0254,
                   "centimeters": 0.01, "cm": 0.01}
    from_meters = {k: 1 / v for k, v in to_meters.items()}

    # ── Weight (base: grams) ─────────────────────────────────
    to_grams    = {"grams": 1, "g": 1, "kilograms": 1000, "kg": 1000,
                   "pounds": 453.592, "lbs": 453.592, "ounces": 28.3495, "oz": 28.3495}
    from_grams  = {k: 1 / v for k, v in to_grams.items()}

    try:
        if f in to_meters and t in to_meters:
            result = value * to_meters[f] * from_meters[t]
            return f"{value} {from_unit} = {round(result, 6)} {to_unit}"

        if f in to_grams and t in to_grams:
            result = value * to_grams[f] * from_grams[t]
            return f"{value} {from_unit} = {round(result, 6)} {to_unit}"

        # Temperature
        if f == "celsius" and t == "fahrenheit":
            return f"{value}°C = {round(value * 9/5 + 32, 2)}°F"
        if f == "fahrenheit" and t == "celsius":
            return f"{value}°F = {round((value - 32) * 5/9, 2)}°C"
        if f == "celsius" and t == "kelvin":
            return f"{value}°C = {round(value + 273.15, 2)} K"
        if f == "kelvin" and t == "celsius":
            return f"{value} K = {round(value - 273.15, 2)}°C"

        return f"Conversion from '{from_unit}' to '{to_unit}' is not supported."
    except Exception as exc:
        return f"Error: {exc}"


TOOLS = [calculator, get_current_datetime, word_counter, unit_converter]


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
        "You are a helpful general-purpose assistant with access to four tools: "
        "a calculator, a datetime tool, a word counter, and a unit converter. "
        "Always use the appropriate tool when the question requires it. "
        "You may call multiple tools in sequence if needed to answer completely."
    ),
)

_runtime_client = RuntimeClient(os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"))


def run_agent(user_input: str) -> dict:
    t0     = time.perf_counter()
    result = invoke_with_runtime(
        agent,
        {"messages": [("human", user_input)]},
        client=_runtime_client,
        name="agent_05_multi_tool",
        metadata={
            "framework": "langchain",
            "agent_id": "agent_05_multi_tool",
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
        "agent":           "agent_05_multi_tool",
        "provider":        PROVIDER,
        "model":           getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":           user_input,
        "output":          output,
        "tool_calls":      tool_calls,
        "tools_available": [t.name for t in TOOLS],
        "latency_ms":      latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1
        else (
            "What is today's date? Also convert 5 miles to kilometers "
            "and tell me how many words are in this sentence: "
            "'The quick brown fox jumps over the lazy dog.'"
        )
    )

    result = run_agent(question)

    print(f"\nProvider        : {result['provider']}  ({result['model']})")
    print(f"Tools available : {result['tools_available']}")
    print(f"Input           : {result['input']}")
    print(f"\nTool calls ({len(result['tool_calls'])}):")
    for i, tc in enumerate(result["tool_calls"], 1):
        print(f"  [{i}] tool={tc['tool']}  input={tc['tool_input']}")
        print(f"       output={tc['tool_output']}")
    print(f"\nOutput  : {result['output']}")
    print(f"Latency : {result['latency_ms']} ms\n")
