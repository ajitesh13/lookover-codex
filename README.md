# lookover-codex

`lookover-codex` is a local-first hackathon prototype for enterprise AI agent safety reviews. It combines:

- `pre-run`: a Python CLI and SDK for static checks plus LangChain/LangGraph runtime capture
- `compliance-engine`: a Go backend that stores traces, evaluates controls, and serves reports
- `web`: a fresh Next.js dashboard with separate pre-run and compliance experiences
- `postgres`: the system of record for traces, evidence, findings, shares, and demo reviewer auth

## Product Shape

- Borrowed from Lookover:
  - `trace_id`, `span_id`, `parent_span_id`
  - nested trace tree navigation
  - trace/span detail drill-down
  - grouped findings for `Violations`, `Gaps`, and `Covered`
- Intentionally rebuilt from scratch:
  - compliance backend
  - control catalog loading
  - evaluation logic
  - dashboard design system

## Monorepo Layout

- `backend/`: Go API, Postgres schema, evaluation engine, report generation
- `python/`: `pre-run` CLI and Python SDK for LangChain/LangGraph
- `controls/`: versioned YAML control catalogs for EU AI Act, GDPR, SOC 2, OWASP LLM, ISO 27001, ISO 42001
- `web/`: Next.js dashboards for `/pre-run`, `/compliance`, `/shared/[shareId]`, and `/login`
- `reports/`: exported audit bundles and report artifacts

## Local Development

1. Copy `.env.example` to `.env` if you want to override defaults.
2. Start the full stack:

```bash
make up
```

3. Open:

- Web UI: `http://localhost:3000`
- API: `http://localhost:8080`
- Postgres: `localhost:5433`
- If `3000` is already in use locally, set `WEB_PORT=3001` before `make up`, `make web`, or `docker compose up`.

## Demo Reviewer Login

- Dummy auth is enabled right now.
- Any email and password pair will create a reviewer session in the web app.
- The seeded reviewer credentials in `.env.example` are there as a convenient fallback for the demo flow, not as a production auth requirement.

## Main Flows

- Pre-run scan:

```bash
cd /Users/ajitesh/lookover-codex/python
python3 -m prerun.cli scan /path/to/agent/project --output ./scan.json
python3 -m prerun.cli publish ./scan.json
```

- Runtime instrumentation:
  - Use the Python SDK wrappers for LangChain and LangGraph to emit trace/span events to the Go API.

- Auditor review:
  - Open `/compliance`
  - Inspect a trace tree
  - Drill into span evidence
  - Review grouped findings and framework crosswalks

## Current Priority

This prototype optimizes for:

1. Accuracy of evidence-backed compliance findings
2. Breadth across EU AI Act, GDPR, SOC 2, OWASP LLM Top 10, ISO 27001, and ISO 42001
3. A clear local demo experience for enterprise agent review
