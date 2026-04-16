"""
agent_07_conversational_memory.py
-----------------------------------
Phase 1 · Agent 7 — Conversational Memory Agent

Multi-turn chat agent that remembers the full conversation history within a
session using RunnableWithMessageHistory + an in-memory ChatMessageHistory store.

Each call to run_turn() is one user turn. The session_id ties turns together.
Inspect `get_session_history(session_id)` to see the full message log at any time.

What your audit SDK should capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ✔ session_id (ties all turns to one conversation)
  ✔ turn number within the session
  ✔ user message for this turn
  ✔ assistant reply for this turn
  ✔ full message history snapshot after each turn
  ✔ memory read (history loaded) vs memory write (new messages appended)
  ✔ latency per turn

Run:
    python agent_07_conversational_memory.py
    LLM_PROVIDER=vertexai python agent_07_conversational_memory.py
    LLM_PROVIDER=googleai python agent_07_conversational_memory.py
"""

import os
import time
import sys
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
#  MEMORY STORE  — persisted to SQLite
# ═══════════════════════════════════════════════════════════════

import os as _os
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory

_DB_PATH = _os.getenv("MEMORY_DB_PATH", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "memory.db"))
_DB_URL  = f"sqlite:///{_DB_PATH}"


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    return SQLChatMessageHistory(session_id=session_id, connection_string=_DB_URL)


# ═══════════════════════════════════════════════════════════════
#  CHAIN WITH HISTORY
# ═══════════════════════════════════════════════════════════════

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful, friendly assistant. You have access to the full "
     "conversation history and should use it to give coherent, contextual answers."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

base_chain = prompt | llm | StrOutputParser()

chain_with_history = RunnableWithMessageHistory(
    base_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)
from lookover_codex_sdk import RuntimeClient, invoke_with_runtime

_runtime_client = RuntimeClient(os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"))


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

def run_turn(user_input: str, session_id: str = "default-session") -> dict:
    """
    Process one user turn within a session.

    Parameters
    ----------
    user_input : str   — The human message for this turn.
    session_id : str   — Groups turns into a single conversation.
    """
    # Snapshot history BEFORE this turn (what was read from memory)
    history_before = [
        {"role": m.type, "content": m.content}
        for m in get_session_history(session_id).messages
    ]
    turn_number = len(history_before) // 2 + 1  # each turn = 1 human + 1 ai

    t0     = time.perf_counter()
    output = invoke_with_runtime(
        chain_with_history,
        {"input": user_input},
        client=_runtime_client,
        name="agent_07_conversational_memory",
        metadata={
            "framework": "langchain",
            "agent_id": "agent_07_conversational_memory",
            "agent_version": "1.0.0",
            "model_provider": PROVIDER,
            "model_id": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "model_version": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "session_id": session_id,
        },
        config={"configurable": {"session_id": session_id}},
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Snapshot history AFTER this turn (what was written to memory)
    history_after = [
        {"role": m.type, "content": m.content}
        for m in get_session_history(session_id).messages
    ]

    return {
        "agent":          "agent_07_conversational_memory",
        "provider":       PROVIDER,
        "model":          getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "session_id":     session_id,
        "turn":           turn_number,
        "input":          user_input,
        "output":         output,
        "history_before": history_before,   # memory READ
        "history_after":  history_after,    # memory WRITE (includes new turn)
        "latency_ms":     latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI — runs a 3-turn demo conversation
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    SESSION = "demo-session-001"

    turns = [
        "Hi! My name is Alex and I'm building an AI audit logging SDK.",
        "What are the most important events I should log for an LLM call?",
        "Can you summarise what you know about me and what we discussed?",
    ]

    print(f"\nProvider : {PROVIDER}")
    print(f"Session  : {SESSION}")
    print("=" * 60)

    for turn_input in turns:
        result = run_turn(turn_input, session_id=SESSION)

        print(f"\n[Turn {result['turn']}]")
        print(f"  User    : {result['input']}")
        print(f"  Agent   : {result['output']}")
        print(f"  Latency : {result['latency_ms']} ms")
        print(f"  History size before → after : "
              f"{len(result['history_before'])} → {len(result['history_after'])} messages")

    print("\n" + "=" * 60)
    final_history = get_session_history(SESSION).messages
    print(f"Full session history ({len(final_history)} messages)  [persisted to {_DB_PATH}]:")
    for msg in final_history:
        role = "User " if msg.type == "human" else "Agent"
        print(f"  [{role}] {msg.content[:100]}{'…' if len(msg.content) > 100 else ''}")
    print()
