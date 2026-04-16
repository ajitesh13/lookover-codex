from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any
from urllib import error, request

from run_hf_dataset_audit import (
    DISCLOSURE_TEXT,
    TranscriptSample,
    build_sample,
    load_local_dataset,
    metadata_bool,
)


DEFAULT_LOOKOVER_API_BASE_URL = "http://localhost:8080"
DEFAULT_OUTPUT = Path("data/reports/lookover_voice_ingest_report.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest local voice transcripts into the Lookover backend voice-runs API."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON, JSONL, TXT file, or a directory containing transcript files.",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_LOOKOVER_API_BASE_URL,
        help="Lookover API base URL that exposes /v1/voice-runs.",
    )
    parser.add_argument("--tenant", default="demo-voice", help="Tenant stamped on created voice runs.")
    parser.add_argument("--deployer", default="voice-ops", help="Deployer stamped on created voice runs.")
    parser.add_argument("--agent-version", default="demo-ingest-v1", help="Agent version stamped on the payload.")
    parser.add_argument("--policy-version", default="policy-demo-ingest-v1", help="Policy version stamped on the payload.")
    parser.add_argument("--language", default="en", help="Language sent to the backend.")
    parser.add_argument("--call-id-prefix", default="demo-call", help="Prefix used when generating call ids.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum number of transcripts to submit.")
    parser.add_argument("--offset", type=int, default=0, help="Number of discovered transcripts to skip.")
    parser.add_argument("--seed", type=int, default=7, help="Shuffle seed applied before offset/limit.")
    parser.add_argument(
        "--mode",
        choices=("baseline", "inject-disclosure"),
        default="baseline",
        help="Whether to send transcripts as-is or prepend a disclosure turn.",
    )
    parser.add_argument(
        "--synthetic-audio-used",
        action="store_true",
        help="Force synthetic_audio_used=true for every payload.",
    )
    parser.add_argument(
        "--synthetic-audio-marked",
        action="store_true",
        help="Force synthetic_audio_marked=true for every payload.",
    )
    parser.add_argument(
        "--human-oversight-path-present",
        action="store_true",
        help="Force human_oversight_path_present=true for every payload.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to the JSON summary report written after ingestion.",
    )
    return parser.parse_args()


def load_samples(input_path: Path, seed: int, offset: int, limit: int) -> list[TranscriptSample]:
    samples = list(iter_samples(input_path))
    rng = random.Random(seed)
    rng.shuffle(samples)
    return samples[offset : offset + limit]


def iter_samples(input_path: Path) -> list[TranscriptSample]:
    if input_path.is_dir():
        return list(load_local_dataset(input_path)) + list(load_text_samples(input_path))

    if input_path.suffix.lower() in {".json", ".jsonl"}:
        return list(load_local_dataset(input_path))

    if input_path.suffix.lower() in {".txt", ".md"}:
        return list(load_text_samples(input_path))

    raise SystemExit(f"Unsupported input path: {input_path}")


def load_text_samples(path: Path) -> list[TranscriptSample]:
    if path.is_dir():
        samples: list[TranscriptSample] = []
        for candidate in sorted(path.rglob("*")):
            if candidate.suffix.lower() not in {".txt", ".md"}:
                continue
            samples.extend(load_text_samples(candidate))
        return samples

    transcript = path.read_text(encoding="utf-8").strip()
    if not transcript:
        return []

    row = {
        "transcript": transcript,
        "raw_audio_uri": f"file://{path.resolve()}",
        "audit_metadata": {},
    }
    sample = build_sample(row, source_id=path.name)
    return [sample] if sample is not None else []


def maybe_inject_disclosure(turns: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode != "inject-disclosure":
        return turns
    return [
        {"speaker": "agent", "text": DISCLOSURE_TEXT, "timestamp_seconds": 0.0},
        *[
            {
                "speaker": turn["speaker"],
                "text": turn["text"],
                "timestamp_seconds": float(turn["timestamp_seconds"]) + 2.0,
            }
            for turn in turns
        ],
    ]


def build_payload(sample: TranscriptSample, index: int, args: argparse.Namespace) -> dict[str, Any]:
    turns = maybe_inject_disclosure(sample.transcript_turns, args.mode)
    transcript = "\n".join(f"{turn['speaker'].title()}: {turn['text']}" for turn in turns)
    audit_metadata = sample.metadata.get("audit_metadata", {})
    source_evidence = audit_metadata.get("source_evidence")
    if not isinstance(source_evidence, dict):
        source_evidence = {}

    return {
        "call_id": f"{args.call_id_prefix}-{index + args.offset:05d}",
        "tenant": args.tenant,
        "deployer": args.deployer,
        "language": args.language,
        "transcript": transcript,
        "agent_version": args.agent_version,
        "policy_version": args.policy_version,
        "raw_audio_uri": sample.raw_audio_uri,
        "synthetic_audio_used": args.synthetic_audio_used
        or metadata_bool(source_evidence, "synthetic_audio_used", args.mode == "inject-disclosure"),
        "synthetic_audio_marked": args.synthetic_audio_marked
        or metadata_bool(source_evidence, "synthetic_audio_marked", args.mode == "inject-disclosure"),
        "deepfake_like_content_flag": metadata_bool(source_evidence, "deepfake_like_content_flag"),
        "emotion_recognition_used": metadata_bool(audit_metadata, "emotion_recognition_used"),
        "biometric_categorisation_used": metadata_bool(audit_metadata, "biometric_categorisation_used"),
        "decision_support_flag": metadata_bool(audit_metadata, "decision_support_flag"),
        "human_oversight_path_present": args.human_oversight_path_present
        or metadata_bool(audit_metadata, "human_oversight_path_present"),
        "notice_to_affected_person_present": metadata_bool(audit_metadata, "notice_to_affected_person_present"),
        "high_risk_flag": metadata_bool(audit_metadata, "high_risk_flag"),
    }


def post_voice_run(api_base_url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | str]:
    endpoint = api_base_url.rstrip("/") + "/v1/voice-runs"
    raw_body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=raw_body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request) as response:
            raw_response = response.read().decode("utf-8")
            return response.status, json.loads(raw_response)
    except error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw_error)
        except json.JSONDecodeError:
            return exc.code, raw_error
    except error.URLError as exc:
        return 0, str(exc)


def run_ingest(samples: list[TranscriptSample], args: argparse.Namespace) -> dict[str, Any]:
    disposition_counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for index, sample in enumerate(samples):
        payload = build_payload(sample, index, args)
        status_code, response_body = post_voice_run(args.api_base_url, payload)
        if status_code != 201 or not isinstance(response_body, dict):
            failures.append(
                {
                    "source_id": sample.source_id,
                    "status_code": status_code,
                    "detail": response_body,
                }
            )
            continue

        disposition = str(response_body.get("disposition", ""))
        disposition_counts[disposition] += 1
        records.append(
            {
                "source_id": sample.source_id,
                "voice_run_id": response_body.get("voice_run_id"),
                "call_id": response_body.get("call_id"),
                "status": response_body.get("status"),
                "disposition": disposition,
                "applicability": response_body.get("applicability"),
                "finding_count": response_body.get("finding_count", len(response_body.get("findings", []))),
            }
        )

    return {
        "api_base_url": args.api_base_url,
        "input": args.input,
        "mode": args.mode,
        "requested_limit": args.limit,
        "offset": args.offset,
        "submitted_records": len(records),
        "failed_records": len(failures),
        "disposition_counts": dict(disposition_counts),
        "failures": failures[:25],
        "records": records[:100],
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    samples = load_samples(Path(args.input), args.seed, args.offset, args.limit)
    if not samples:
        raise SystemExit(f"No ingestible transcripts found under {args.input}")

    report = run_ingest(samples, args)
    output_path = Path(args.output)
    write_report(report, output_path)
    print(json.dumps(report, indent=2))
    print(f"\nWrote ingest report to {output_path}")


if __name__ == "__main__":
    main()
