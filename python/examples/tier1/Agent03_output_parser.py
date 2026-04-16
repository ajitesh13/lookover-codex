"""
agent_03_output_parser.py
--------------------------
Phase 1 · Agent 3 — Output Parser Agent

Prompt → LLM → JsonOutputParser → validated Pydantic model.
Also captures parse failures so your SDK can log both success and error paths.

Run:
    python agent_03_output_parser.py
    LLM_PROVIDER=vertexai python agent_03_output_parser.py
    LLM_PROVIDER=googleai python agent_03_output_parser.py
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
    agent_id="agent_03_output_parser",
    agent_version="1.0.0",
    base_url=os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"),
    model_provider=PROVIDER,
    model_version=getattr(llm, "model", getattr(llm, "model_name", "unknown")),
)


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException


class TechConceptSummary(BaseModel):
    concept:        str       = Field(description="Name of the concept")
    one_liner:      str       = Field(description="One sentence definition")
    key_components: list[str] = Field(description="3-5 key components")
    use_cases:      list[str] = Field(description="2-3 real-world use cases")
    difficulty:     str       = Field(description="beginner | intermediate | advanced")


SYSTEM_MSG = (
    "You are a technical knowledge assistant. "
    "Always respond with ONLY valid JSON matching the requested schema. "
    "Do NOT include markdown code fences or any extra text."
)
HUMAN_MSG = (
    "Provide a structured summary of: '{concept}'.\n\n"
    "Return ONLY a JSON object with keys:\n"
    "  concept, one_liner, key_components (list), use_cases (list), difficulty"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_MSG),
    ("human",  HUMAN_MSG),
])

parser = JsonOutputParser(pydantic_object=TechConceptSummary)
chain  = prompt | llm | parser


def run_agent(concept: str) -> dict:
    parse_success = True
    parse_error   = None
    parsed_output = None

    t0 = time.perf_counter()
    try:
        parsed_output = chain.invoke({"concept": concept}, config={"callbacks": [_lookover]})
    except OutputParserException as exc:
        parse_success = False
        parse_error   = str(exc)
    finally:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "agent":         "agent_03_output_parser",
        "provider":      PROVIDER,
        "model":         getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input_concept": concept,
        "parse_success": parse_success,
        "parsed_output": parsed_output,
        "parse_error":   parse_error,
        "latency_ms":    latency_ms,
        "parser":        "JsonOutputParser",
        "output_schema": TechConceptSummary.model_json_schema(),
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    concept = sys.argv[1] if len(sys.argv) > 1 else "Retrieval-Augmented Generation"

    result = run_agent(concept)

    print(f"\nProvider : {result['provider']}  ({result['model']})")
    print(f"Concept  : {result['input_concept']}")

    if result["parse_success"]:
        po = result["parsed_output"]
        print(f"\n✔ Parse succeeded")
        print(f"  one_liner      : {po.get('one_liner')}")
        print(f"  difficulty     : {po.get('difficulty')}")
        print(f"  key_components : {po.get('key_components')}")
        print(f"  use_cases      : {po.get('use_cases')}")
    else:
        print(f"\n✘ Parse FAILED: {result['parse_error']}")

    print(f"\nLatency  : {result['latency_ms']} ms\n")
