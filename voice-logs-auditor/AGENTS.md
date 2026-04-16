# Repository Guidelines

## Project Structure & Module Organization

Core application code lives in `app/`. Use `app/main.py` for the FastAPI entrypoint, `app/routes/` for JSON and HTML endpoints, `app/services/` for audit orchestration, `app/storage/` for SQLite and evidence persistence, and `app/compliance/` for deterministic rules. Templates and static assets are in `templates/` and `static/`. Tests live in `tests/`. Utility scripts such as dataset replay and report generation live in `scripts/`. Runtime data is written under `data/`, including `data/evidence/`, `data/reports/`, and `data/voice_logs_auditor.db`.

## Build, Test, and Development Commands

Create a local environment with `python3.13 -m venv .venv` and `source .venv/bin/activate`, then install dependencies with `pip install -e ".[dev]"`. Run the app locally with `uvicorn app.main:app --reload` and open `http://127.0.0.1:8000`. Run the full test suite with `pytest`. Replay the bundled Hugging Face audit workflow with:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_hf_dataset_audit.py --split train --limit 25
```

## Coding Style & Naming Conventions

Follow the existing Python style: 4-space indentation, type hints, and small focused modules. Use `snake_case` for functions, variables, and test names; use `PascalCase` for Pydantic models and service classes. Keep route handlers thin and move business logic into `app/services/` or `app/compliance/`. There is no configured formatter or linter in `pyproject.toml`, so keep formatting consistent with the surrounding file before submitting changes.

## Testing Guidelines

Tests use `pytest` with shared fixtures in `tests/conftest.py`. Name files `test_*.py` and keep test functions behavior-oriented, for example `test_healthcheck_returns_ok`. Prefer `tmp_path`-backed repository fixtures so tests do not write into the checked-in `data/` directory. Add or update API coverage whenever route contracts, persistence behavior, or compliance rules change.

## Commit & Pull Request Guidelines

Recent history mixes concise imperative messages and conventional prefixes such as `feat:` and `fix(web):`. Follow that pattern: keep subjects short, specific, and action-oriented. Pull requests should describe the behavior change, list test coverage run locally, and include screenshots when HTML templates or dashboard views change. Link the relevant issue or task when one exists.

## Security & Configuration Tips

Do not commit generated SQLite databases, evidence JSON, or ad hoc report outputs from `data/`. Treat tenant IDs, call IDs, and file paths as untrusted input; preserve the existing validation behavior when extending APIs or storage paths.
