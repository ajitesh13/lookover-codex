from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
DATABASE_PATH = DATA_DIR / "voice_logs_auditor.db"
SAMPLE_PAYLOAD_DIR = DATA_DIR / "sample_payloads"


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
