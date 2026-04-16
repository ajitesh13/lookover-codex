# Voice Logs Auditor

FastAPI reference implementation for post-call EU AI Act voice audit analysis.

## What it does

- Ingests voice call metadata, transcript turns, and governance links
- Persists append-only audit records as JSON plus indexed SQLite metadata
- Runs deterministic compliance checks for selected EU AI Act articles
- Exposes JSON APIs and a small HTML interface for manual testing
- Supports re-analysis, legal hold, evidence bundle export, and finding filters

## Quickstart

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Run tests

```bash
pytest
```

## Replay a Hugging Face call-center dataset

The repo includes a dataset replay harness at `scripts/run_hf_dataset_audit.py` that can stream
the Hugging Face dataset `shadye-6/92k-real-world-call-center-scripts-english` through the audit API
using an in-process FastAPI test client.

Install the extra loader dependency first:

```bash
pip install datasets
```

Then run:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_hf_dataset_audit.py \
  --hf-dataset shadye-6/92k-real-world-call-center-scripts-english \
  --split train \
  --limit 25 \
  --mode inject-disclosure
```

The script writes a JSON report to `data/reports/hf_dataset_audit_report.json` by default.

## Project layout

- `app/main.py`: FastAPI entrypoint
- `app/models.py`: Pydantic models and enums
- `app/services/audit_service.py`: orchestration for ingest, re-analysis, retrieval
- `app/storage/repository.py`: SQLite plus append-only JSON persistence
- `app/compliance/rules.py`: applicability classifier and compliance checks
- `templates/`: HTML test pages
- `data/sample_payloads/`: example audit inputs

## Storage

By default the app writes:

- SQLite index: `data/voice_logs_auditor.db`
- Evidence JSON: `data/evidence/<tenant>/<call_id>/v<version>.json`

Each re-analysis creates a new evidence version and leaves prior versions intact.
