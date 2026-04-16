"""
agent_06_rag.py
----------------
Phase 1 · Agent 6 — RAG Agent (Retrieval-Augmented Generation)

Loads a small in-memory document corpus → embeds with a local or cloud
embedder → stores in a FAISS vector store → retrieval chain answers
questions by fetching the most relevant chunks and passing them to the LLM.

No external services required for the vector store (FAISS runs locally).
Embeddings are handled per provider:
  ollama   → OllamaEmbeddings  (uses the same remote Ollama server)
  vertexai → VertexAIEmbeddings
  googleai → GoogleGenerativeAIEmbeddings

Run:
    python agent_06_rag.py
    LLM_PROVIDER=vertexai python agent_06_rag.py
    LLM_PROVIDER=googleai python agent_06_rag.py
"""

import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  LLM + EMBEDDINGS SETUP
# ═══════════════════════════════════════════════════════════════

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

if PROVIDER == "ollama":
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    llm = ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.1.17:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        temperature=0.0,
    )
    embeddings = OllamaEmbeddings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.1.17:11434"),
        model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    )

elif PROVIDER == "vertexai":
    from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings
    llm = ChatVertexAI(
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        model_name=os.getenv("VERTEXAI_MODEL", "gemini-1.5-flash-002"),
        temperature=0.0,
    )
    embeddings = VertexAIEmbeddings(
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        model_name="text-embedding-004",
    )

elif PROVIDER == "googleai":
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLEAI_MODEL", "gemini-2.5-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

else:
    raise ValueError(f"Unknown LLM_PROVIDER='{PROVIDER}'. Use 'ollama', 'vertexai', or 'googleai'.")


# ═══════════════════════════════════════════════════════════════
#  DOCUMENT CORPUS  — loaded from docs/ directory on disk
# ═══════════════════════════════════════════════════════════════

import os as _os
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lookover_codex_sdk import RuntimeClient, invoke_with_runtime

_DOCS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "docs")

print(f"[RAG] Loading documents from {_DOCS_DIR} …")
_loader = DirectoryLoader(_DOCS_DIR, glob="*.txt", loader_cls=TextLoader)
_raw_docs = _loader.load()

_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
DOCUMENTS = _splitter.split_documents(_raw_docs)
print(f"[RAG] Loaded {len(_raw_docs)} files → {len(DOCUMENTS)} chunks")


# ═══════════════════════════════════════════════════════════════
#  VECTOR STORE + RETRIEVER
# ═══════════════════════════════════════════════════════════════

from langchain_community.vectorstores import FAISS

print("[RAG] Building FAISS vector store from corpus …")
vector_store = FAISS.from_documents(DOCUMENTS, embeddings)
retriever    = vector_store.as_retriever(search_kwargs={"k": 3})


# ═══════════════════════════════════════════════════════════════
#  RAG CHAIN
# ═══════════════════════════════════════════════════════════════

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful assistant. Answer the question using ONLY the context provided below. "
     "If the answer is not in the context, say 'I don't have enough information to answer that.'\n\n"
     "Context:\n{context}"),
    ("human", "{question}"),
])


def format_docs(docs: list[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | RAG_PROMPT
    | llm
    | StrOutputParser()
)

_runtime_client = RuntimeClient(os.getenv("LOOKOVER_BASE_URL", "http://localhost:8080"))


def run_agent(user_input: str) -> dict:
    # Retrieve docs separately so we can log them
    t_retrieve = time.perf_counter()
    retrieved_docs = invoke_with_runtime(
        retriever,
        user_input,
        client=_runtime_client,
        name="agent_06_rag_retriever",
        metadata={
            "framework": "langchain",
            "agent_id": "agent_06_rag",
            "agent_version": "1.0.0",
            "model_provider": PROVIDER,
            "model_id": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "model_version": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "component": "retriever",
        },
    )
    retrieve_ms = round((time.perf_counter() - t_retrieve) * 1000, 2)

    retrieved_chunks = [
        {
            "content":  doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in retrieved_docs
    ]

    # Full chain (retrieval + generation)
    t0     = time.perf_counter()
    output = invoke_with_runtime(
        rag_chain,
        user_input,
        client=_runtime_client,
        name="agent_06_rag_chain",
        metadata={
            "framework": "langchain",
            "agent_id": "agent_06_rag",
            "agent_version": "1.0.0",
            "model_provider": PROVIDER,
            "model_id": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "model_version": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
            "component": "rag_chain",
        },
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "agent":            "agent_06_rag",
        "provider":         PROVIDER,
        "model":            getattr(llm, "model", getattr(llm, "model_name", "unknown")),
        "input":            user_input,
        "output":           output,
        "retrieved_chunks": retrieved_chunks,
        "num_chunks":       len(retrieved_chunks),
        "retrieve_ms":      retrieve_ms,
        "latency_ms":       latency_ms,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1
        else "What is LangGraph and how does it differ from LangChain?"
    )

    result = run_agent(question)

    print(f"\nProvider          : {result['provider']}  ({result['model']})")
    print(f"Input             : {result['input']}")
    print(f"\nRetrieved chunks ({result['num_chunks']})  [{result['retrieve_ms']} ms]:")
    for i, chunk in enumerate(result["retrieved_chunks"], 1):
        print(f"  [{i}] source={chunk['metadata'].get('source')}  "
              f"preview={chunk['content'][:80]}…")
    print(f"\nOutput  : {result['output']}")
    print(f"Latency : {result['latency_ms']} ms  (full chain)\n")
