from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from types import SimpleNamespace

from app.compliance.rules import (
    build_compliance_evidence,
    build_event_timeline,
    classify_applicability,
    evaluate_findings,
    overall_disposition,
)
from app.models import AuditIngestRequest
from scripts.run_hf_dataset_audit import build_payload, build_sample


DEFAULT_DATASET_DIR = Path("/tmp/hf_audit_extract/medicare_inbound")
DEFAULT_HTML_OUTPUT = Path("data/reports/hf_random_100_detailed.html")
DEFAULT_JSON_OUTPUT = Path("data/reports/hf_random_100_detailed.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a random sample of local HF transcripts and write a detailed HTML report.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR), help="Directory containing transcript JSON files.")
    parser.add_argument("--limit", type=int, default=100, help="Number of valid random records to audit.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed used for sampling.")
    parser.add_argument("--mode", choices=("baseline", "inject-disclosure"), default="baseline")
    parser.add_argument("--tenant", default="hf-html")
    parser.add_argument("--deployer", default="voice-ops")
    parser.add_argument("--agent-version", default="hf-random-html-v1")
    parser.add_argument("--policy-version", default="policy-hf-random-html")
    parser.add_argument("--html-output", default=str(DEFAULT_HTML_OUTPUT))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    return parser.parse_args()


def load_random_samples(dataset_dir: Path, limit: int, seed: int) -> list:
    candidates = sorted(path for path in dataset_dir.glob("*.json") if not path.name.startswith("._"))
    rng = random.Random(seed)
    rng.shuffle(candidates)

    samples = []
    for path in candidates:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        sample = build_sample(row, source_id=f"{path.name}:0")
        if sample is not None:
            samples.append(sample)
        if len(samples) >= limit:
            break
    return samples


def audit_samples(samples: list, args: argparse.Namespace) -> dict[str, object]:
    article_status_counts: Counter[str] = Counter()
    disposition_counts: Counter[str] = Counter()
    detailed_records: list[dict[str, object]] = []

    payload_args = SimpleNamespace(
        mode=args.mode,
        tenant=args.tenant,
        deployer=args.deployer,
        agent_version=args.agent_version,
        policy_version=args.policy_version,
    )

    for index, sample in enumerate(samples):
        payload_dict = build_payload(sample, index, payload_args)
        payload = AuditIngestRequest.model_validate(payload_dict)
        applicability = classify_applicability(payload)
        evidence = build_compliance_evidence(payload, applicability)
        findings = evaluate_findings(payload, applicability, evidence)
        timeline = build_event_timeline(payload, evidence)
        disposition = overall_disposition(findings)
        disposition_counts[disposition] += 1

        for finding in findings:
            article_status_counts[f"{finding.article}:{finding.status.value}"] += 1

        detailed_records.append(
            {
                "source_id": sample.source_id,
                "call_id": payload.call_id,
                "disposition": disposition,
                "applicability": applicability.value,
                "started_at": payload.started_at.isoformat(),
                "ai_disclosure_status": evidence.ai_disclosure_status,
                "disclosure_timestamp": evidence.disclosure_timestamp,
                "transcript_preview": sample.transcript_turns[:6],
                "timeline": timeline,
                "findings": [finding.model_dump(mode="json") for finding in findings],
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_dir": str(args.dataset_dir),
        "limit": args.limit,
        "seed": args.seed,
        "mode": args.mode,
        "audited_records": len(detailed_records),
        "disposition_counts": dict(disposition_counts),
        "article_status_counts": dict(article_status_counts),
        "records": detailed_records,
    }


def _render_summary_cards(report: dict[str, object]) -> str:
    items = [
        ("Audited Records", str(report["audited_records"])),
        ("Mode", str(report["mode"])),
        ("Seed", str(report["seed"])),
        ("Dataset", escape(str(report["dataset_dir"]))),
    ]
    disposition_counts = report["disposition_counts"]
    for key in ("pass", "needs_review", "soft_fail", "hard_fail"):
        if key in disposition_counts:
            items.append((key.replace("_", " ").title(), str(disposition_counts[key])))

    return "".join(
        f'<div class="stat-card"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
        for label, value in items
    )


def _render_article_counts(report: dict[str, object]) -> str:
    rows = []
    for key, value in sorted(report["article_status_counts"].items()):
        article, status = key.split(":", 1)
        rows.append(
            f"<tr><td>{escape(article)}</td><td>{escape(status)}</td><td>{value}</td></tr>"
        )
    return "".join(rows)


def _render_disposition_cards(report: dict[str, object]) -> str:
    cards = []
    for key in ("hard_fail", "soft_fail", "needs_review", "pass"):
        if key not in report["disposition_counts"]:
            continue
        cards.append(
            f'<div class="dispo-card {escape(key)}"><div class="label">{escape(key.replace("_", " "))}</div>'
            f'<div class="value">{report["disposition_counts"][key]}</div></div>'
        )
    return "".join(cards)


def _render_record(record: dict[str, object]) -> str:
    transcript_lines = "".join(
        f'<div class="turn"><span class="speaker">{escape(turn["speaker"])}</span><span class="text">{escape(turn["text"])}</span></div>'
        for turn in record["transcript_preview"]
    )
    timeline = "".join(
        f'<li><strong>{escape(str(item["event"]))}</strong><span>{escape(str(item["timestamp_seconds"]))}s</span></li>'
        for item in record["timeline"]
    )
    findings = "".join(
        "<tr>"
        f"<td>{escape(str(finding['article']))}</td>"
        f"<td>{escape(str(finding['status']))}</td>"
        f"<td>{escape(str(finding['severity']))}</td>"
        f"<td>{escape(str(finding['reason']))}</td>"
        "</tr>"
        for finding in record["findings"]
    )
    disclosure_value = "missing" if record["disclosure_timestamp"] is None else f"{record['disclosure_timestamp']}s"
    return (
        '<details class="record">'
        '<summary class="record-head">'
        f'<div><div class="record-kicker">Case File</div><h3>{escape(str(record["call_id"]))}</h3>'
        f'<p class="meta">Source: {escape(str(record["source_id"]))} | Applicability: {escape(str(record["applicability"]))}</p></div>'
        f'<div class="record-badges"><span class="pill {escape(str(record["disposition"]))}">{escape(str(record["disposition"]))}</span>'
        f'<span class="micro-pill">Disclosure: {escape(str(record["ai_disclosure_status"]))}</span>'
        f'<span class="micro-pill">Timestamp: {escape(disclosure_value)}</span></div>'
        '</summary>'
        '<div class="record-body">'
        '<div class="record-grid">'
        f'<section class="subpanel"><div class="section-cap">Transcript Preview</div>{transcript_lines}</section>'
        f'<section class="subpanel"><div class="section-cap">Event Timeline</div><ul class="timeline">{timeline}</ul></section>'
        '</div>'
        '<section class="subpanel findings-panel"><div class="section-cap">Findings Matrix</div>'
        '<table><thead><tr><th>Article</th><th>Status</th><th>Severity</th><th>Reason</th></tr></thead>'
        f"<tbody>{findings}</tbody></table></section>"
        "</div></details>"
    )


def render_html(report: dict[str, object]) -> str:
    records_html = "".join(_render_record(record) for record in report["records"])
    article_rows = _render_article_counts(report)
    summary_cards = _render_summary_cards(report)
    disposition_cards = _render_disposition_cards(report)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HF Random Audit Detailed Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d12;
      --bg2: #0e1520;
      --surface: rgba(12, 19, 29, 0.88);
      --surface2: rgba(18, 28, 41, 0.94);
      --surface3: rgba(11, 17, 27, 0.78);
      --border: rgba(143, 171, 204, 0.22);
      --border2: rgba(121, 146, 177, 0.12);
      --text: #f3efe6;
      --muted: #97a9bf;
      --faint: #607287;
      --accent: #73b6ff;
      --accent2: #f1b45b;
      --pass: #3a9369;
      --needs_review: #d0933a;
      --soft_fail: #cb6a4b;
      --hard_fail: #d14f5c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Fraunces", Georgia, serif;
      background:
        radial-gradient(circle at top right, rgba(115, 182, 255, 0.12), transparent 22%),
        radial-gradient(circle at left center, rgba(209, 79, 92, 0.08), transparent 28%),
        linear-gradient(180deg, #05080c 0%, var(--bg) 24%, var(--bg2) 100%);
      color: var(--text);
      line-height: 1.45;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 100% 4px;
      opacity: 0.06;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ margin: 0 0 12px; color: var(--muted); }}
    .strip {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 18px;
      padding: 10px 16px;
      border: 1px solid var(--border);
      border-radius: 999px;
      backdrop-filter: blur(18px);
      background: rgba(9, 13, 18, 0.82);
      font: 500 11px/1.2 "IBM Plex Mono", monospace;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at top left, rgba(115, 182, 255, 0.18), transparent 32%),
        linear-gradient(145deg, rgba(12, 19, 29, 0.96), rgba(14, 21, 32, 0.92));
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 30px;
      margin-bottom: 24px;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.34);
    }}
    .hero::after {{
      content: "DOSSIER";
      position: absolute;
      right: 22px;
      top: 8px;
      font: 400 clamp(56px, 10vw, 130px)/0.9 "Bebas Neue", sans-serif;
      letter-spacing: 0.08em;
      color: rgba(255,255,255,0.03);
    }}
    .eyebrow {{
      font: 500 11px/1.2 "IBM Plex Mono", monospace;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: var(--accent2);
      margin-bottom: 14px;
    }}
    .hero h1 {{
      max-width: 860px;
      font: 400 clamp(40px, 7vw, 92px)/0.92 "Bebas Neue", sans-serif;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .hero p {{
      max-width: 760px;
      font-size: 15px;
      color: #bfd0e2;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .stat-card, .dispo-card {{
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .stat-card:hover, .dispo-card:hover, .record:hover {{
      transform: translateY(-2px);
      border-color: rgba(115, 182, 255, 0.34);
      box-shadow: 0 16px 28px rgba(0, 0, 0, 0.28);
    }}
    .label {{
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.2em;
      color: var(--muted);
    }}
    .value {{
      margin-top: 6px;
      font: 400 clamp(26px, 4vw, 46px)/0.95 "Bebas Neue", sans-serif;
      letter-spacing: 0.03em;
    }}
    .section-block {{
      margin-bottom: 22px;
    }}
    .section-head {{
      display: flex;
      align-items: baseline;
      gap: 14px;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border2);
    }}
    .section-no {{
      font: 400 26px/1 "Bebas Neue", sans-serif;
      color: var(--accent2);
      letter-spacing: 0.08em;
    }}
    .section-title {{
      font: 400 26px/1.05 "Fraunces", serif;
    }}
    .section-tag {{
      margin-left: auto;
      padding: 4px 8px;
      border: 1px solid var(--border);
      border-radius: 999px;
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 18px 36px rgba(0, 0, 0, 0.24);
    }}
    .dispo-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .dispo-card.pass {{ border-left: 4px solid var(--pass); }}
    .dispo-card.needs_review {{ border-left: 4px solid var(--needs_review); }}
    .dispo-card.soft_fail {{ border-left: 4px solid var(--soft_fail); }}
    .dispo-card.hard_fail {{ border-left: 4px solid var(--hard_fail); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 11px 8px; border-bottom: 1px solid var(--border2); vertical-align: top; }}
    th {{
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--muted);
    }}
    td {{ color: #dbe5ef; font-size: 14px; }}
    .record {{
      background: linear-gradient(180deg, var(--surface), var(--surface3));
      border: 1px solid var(--border);
      border-radius: 20px;
      margin-bottom: 16px;
      overflow: hidden;
      box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .record[open] {{ border-color: rgba(115, 182, 255, 0.36); }}
    .record-head {{
      list-style: none;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding: 18px 20px;
      cursor: pointer;
    }}
    .record-head::-webkit-details-marker {{ display: none; }}
    .record-head h3 {{
      font: 400 26px/1 "Bebas Neue", sans-serif;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .record-kicker {{
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      color: var(--accent2);
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .record-badges {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }}
    .record-body {{
      padding: 0 20px 20px;
    }}
    .record-grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .subpanel {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border2);
      border-radius: 16px;
      padding: 16px;
    }}
    .findings-panel {{
      overflow-x: auto;
    }}
    .section-cap {{
      margin-bottom: 12px;
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }}
    .meta {{ color: var(--muted); font-size: 13px; margin: 0; }}
    .pill, .micro-pill {{
      border-radius: 999px;
      padding: 6px 10px;
      color: #fff;
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .micro-pill {{
      color: var(--muted);
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border2);
    }}
    .pass {{ background: var(--pass); }}
    .needs_review {{ background: var(--needs_review); }}
    .soft_fail {{ background: var(--soft_fail); }}
    .hard_fail {{ background: var(--hard_fail); }}
    .turn {{
      display: grid;
      grid-template-columns: 84px 1fr;
      gap: 12px;
      padding: 9px 0;
      border-bottom: 1px dashed rgba(151, 169, 191, 0.16);
    }}
    .speaker {{
      color: var(--accent2);
      font: 500 10px/1.2 "IBM Plex Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      padding-top: 4px;
    }}
    .text {{
      color: #e6edf5;
      font-size: 14px;
    }}
    .timeline {{
      margin: 0;
      padding-left: 0;
      list-style: none;
    }}
    .timeline li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 0;
      border-bottom: 1px dashed rgba(151, 169, 191, 0.16);
      color: #d5e0eb;
    }}
    .timeline span {{
      color: var(--accent2);
      font-family: "IBM Plex Mono", monospace;
      font-size: 12px;
    }}
    .foot {{
      margin-top: 20px;
      color: var(--faint);
      font: 500 11px/1.5 "IBM Plex Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    @media (max-width: 800px) {{
      .record-grid {{ grid-template-columns: 1fr; }}
      .record-head {{ flex-direction: column; }}
      .record-badges {{ justify-content: flex-start; }}
    }}
    @media (max-width: 640px) {{
      main {{ padding: 20px 14px 44px; }}
      .hero {{ padding: 22px; }}
      .cards, .dispo-grid {{ grid-template-columns: 1fr 1fr; }}
      .strip {{ border-radius: 18px; flex-direction: column; }}
    }}
    @media print {{
      body {{
        background: white;
        color: #111;
      }}
      body::before {{ display: none; }}
      .strip, .hero, .panel, .record, .subpanel {{
        background: white;
        color: #111;
        box-shadow: none;
        border-color: #ccc;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="strip">
      <span>Voice Logs Auditor</span>
      <span>Compliance Dossier</span>
      <span>Generated {escape(str(report["generated_at"]))}</span>
    </div>
    <section class="hero">
      <div class="eyebrow">EU AI Act · Random Transcript Review · Internal Use</div>
      <h1>Hugging Face Audit Dossier</h1>
      <p>This report audits a sampled transcript set using the current Voice Logs Auditor rule engine. The layout is intentionally dossier-like: high-level signal first, then article counts, then expandable case files with transcript evidence and full findings.</p>
      <div class="cards">{summary_cards}</div>
    </section>
    <section class="section-block">
      <div class="section-head">
        <div class="section-no">01</div>
        <div class="section-title">Disposition Overview</div>
        <div class="section-tag">Priority Signal</div>
      </div>
      <div class="dispo-grid">{disposition_cards}</div>
    </section>
    <section class="section-block">
      <div class="section-head">
        <div class="section-no">02</div>
        <div class="section-title">Article Status Counts</div>
        <div class="section-tag">Rule Breakdown</div>
      </div>
      <section class="panel">
        <table>
          <thead><tr><th>Article</th><th>Status</th><th>Count</th></tr></thead>
          <tbody>{article_rows}</tbody>
        </table>
      </section>
    </section>
    <section class="section-block">
      <div class="section-head">
        <div class="section-no">03</div>
        <div class="section-title">Case Files</div>
        <div class="section-tag">Evidence Review</div>
      </div>
      {records_html}
    </section>
    <p class="foot">This HTML report includes only a short transcript preview for each audited record. Full raw source transcripts remain in the local dataset directory.</p>
  </main>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    args.dataset_dir = Path(args.dataset_dir)
    samples = load_random_samples(args.dataset_dir, args.limit, args.seed)
    if not samples:
        raise SystemExit("No usable samples found in the selected dataset directory.")

    report = audit_samples(samples, args)
    json_output = Path(args.json_output)
    html_output = Path(args.html_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote JSON report to {json_output}")
    print(f"Wrote HTML report to {html_output}")
    print(f"Audited {report['audited_records']} records")
    print(f"Disposition counts: {report['disposition_counts']}")


if __name__ == "__main__":
    main()
