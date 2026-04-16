"""
agent_02_prompt_template.py
-----------------------------
Phase 1 · Agent 2 — Prompt Template Agent

Dynamic ChatPromptTemplate with variables → LLM → string output via LCEL.

Run:
    python agent_02_prompt_template.py
    LLM_PROVIDER=vertexai python agent_02_prompt_template.py
    LLM_PROVIDER=googleai python agent_02_prompt_template.py
"""

import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LLM SETUP  —  set LLM_PROVIDER=ollama (default) or vertexai
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

from lookover_codex_sdk.langchain import LookoverCallbackHandler

_lookover = LookoverCallbackHandler(
    api_key=os.getenv("LOOKOVER_API_KEY", "lk_dev_local"),
    agent_id="agent_02_prompt_template",
    agent_version="1.0.0",
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

SYSTEM_TEMPLATE = (
    "You are an expert technical writer who creates concise explanations "
    "tailored to the knowledge level of the intended audience."
)
HUMAN_TEMPLATE = (
    "Write a short explanation (3-4 sentences) about '{topic}' "
    "aimed at a {audience} audience."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TEMPLATE),
    ("human",  HUMAN_TEMPLATE),
])

chain = prompt | llm | StrOutputParser()


def run_agent(topic: str, audience: str) -> dict:
    template_vars = {"topic": topic, "audience": audience}

    # Capture the fully-rendered prompt your SDK should log
    rendered = "\n".join(
        f"[{m.type.upper()}] {m.content}"
        for m in prompt.format_messages(**template_vars)
    )

    t0 = time.perf_counter()
    output = chain.invoke(template_vars, config={"callbacks": [_lookover]})
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "agent":           "agent_02_prompt_template",
        "provider":        PROVIDER,
        "model":           getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "template_vars":   template_vars,
        "system_template": SYSTEM_TEMPLATE,
        "human_template":  HUMAN_TEMPLATE,
        "rendered_prompt": rendered,
        "output":          output,
        "latency_ms":      latency_ms,
        "parser":          "StrOutputParser",
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    topic    = sys.argv[1] if len(sys.argv) > 1 else "transformer neural networks"
    audience = sys.argv[2] if len(sys.argv) > 2 else "beginner"

    result = run_agent(topic, audience)

    print(f"\nProvider        : {result['provider']}  ({result['model']})")
    print(f"Template vars   : {result['template_vars']}")
    print(f"\nRendered prompt :\n{result['rendered_prompt']}")
    print(f"\nOutput          : {result['output']}")
    print(f"Latency         : {result['latency_ms']} ms\n")
