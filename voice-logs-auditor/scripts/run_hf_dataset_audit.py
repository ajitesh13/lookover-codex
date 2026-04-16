from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Iterable
from urllib import error, request


DEFAULT_DATASET_ID = "shadye-6/92k-real-world-call-center-scripts-english"
DEFAULT_LOOKOVER_API_BASE_URL = "http://localhost:8080"
DISCLOSURE_TEXT = "Hello, I am an AI assistant calling on behalf of the service team."


@dataclass
class TranscriptSample:
    source_id: str
    transcript_turns: list[dict[str, Any]]
    raw_audio_uri: str
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a Hugging Face call-center transcript dataset through the Voice Logs Auditor."
    )
    parser.add_argument("--hf-dataset", default=DEFAULT_DATASET_ID, help="Hugging Face dataset repo id.")
    parser.add_argument("--dataset-path", help="Optional local JSON or JSONL file/directory override.")
    parser.add_argument("--split", default="train", help="Dataset split to load when using Hugging Face.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum number of samples to audit.")
    parser.add_argument("--offset", type=int, default=0, help="Number of source samples to skip before testing.")
    parser.add_argument("--seed", type=int, default=7, help="Shuffle seed applied after loading local samples.")
    parser.add_argument(
        "--mode",
        choices=("baseline", "inject-disclosure"),
        default="inject-disclosure",
        help="Whether to submit samples as-is or prepend a disclosure turn for positive-path testing.",
    )
    parser.add_argument("--tenant", default="hf-eval", help="Tenant used for created audits.")
    parser.add_argument("--deployer", default="voice-ops", help="Deployer value used for created audits.")
    parser.add_argument("--agent-version", default="hf-replay-v1", help="Agent version stamped on test audits.")
    parser.add_argument("--policy-version", default="policy-hf-replay", help="Policy version stamped on test audits.")
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_LOOKOVER_API_BASE_URL,
        help="Lookover public API base URL that exposes /v1/voice-runs.",
    )
    parser.add_argument(
        "--output",
        default="data/reports/hf_dataset_audit_report.json",
        help="Where to write the JSON summary report.",
    )
    return parser.parse_args()


def load_samples(args: argparse.Namespace) -> list[TranscriptSample]:
    if args.dataset_path:
        samples = list(load_local_dataset(Path(args.dataset_path)))
    else:
        samples = list(load_hugging_face_dataset(args.hf_dataset, args.split, args.limit + args.offset))

    rng = random.Random(args.seed)
    rng.shuffle(samples)
    return samples[args.offset : args.offset + args.limit]


def load_hugging_face_dataset(dataset_id: str, split: str, sample_cap: int) -> Iterable[TranscriptSample]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "The 'datasets' package is required for Hugging Face loading. "
            "Install it with: pip install datasets"
        ) from exc

    stream = load_dataset(dataset_id, split=split, streaming=True)
    for index, row in enumerate(islice(stream, sample_cap)):
        sample = build_sample(row, source_id=f"{dataset_id}:{split}:{index}")
        if sample is not None:
            yield sample


def load_local_dataset(path: Path) -> Iterable[TranscriptSample]:
    if path.is_dir():
        for candidate in sorted(path.rglob("*")):
            if candidate.suffix.lower() in {".json", ".jsonl"}:
                yield from load_local_dataset(candidate)
        return

    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue
                sample = build_sample(json.loads(line), source_id=f"{path.name}:{index}")
                if sample is not None:
                    yield sample
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    for index, row in enumerate(rows):
        sample = build_sample(row, source_id=f"{path.name}:{index}")
        if sample is not None:
            yield sample


def build_sample(row: Any, source_id: str) -> TranscriptSample | None:
    if not isinstance(row, dict):
        return None

    transcript_turns = extract_transcript_turns(row)
    if not transcript_turns:
        return None

    raw_audio_uri = first_string(
        row,
        "raw_audio_uri",
        "audio_uri",
        "audio_url",
        "audio_filepath",
        "audio_path",
        default=f"hf://{source_id}",
    )
    return TranscriptSample(
        source_id=source_id,
        transcript_turns=transcript_turns,
        raw_audio_uri=raw_audio_uri,
        metadata=extract_sample_metadata(row),
    )


def extract_sample_metadata(row: dict[str, Any]) -> dict[str, Any]:
    audit_metadata = row.get("audit_metadata")
    if not isinstance(audit_metadata, dict):
        audit_metadata = {}

    metadata = {
        "keys": sorted(row.keys())[:25],
        "case_id": first_string(row, "case_id") or first_string(audit_metadata, "case_id"),
        "scenario": first_string(row, "scenario") or first_string(audit_metadata, "scenario"),
        "risk_type": first_string(row, "risk_type") or first_string(audit_metadata, "risk_type"),
        "expected_disposition": first_string(row, "expected_disposition")
        or first_string(audit_metadata, "expected_disposition"),
        "audit_metadata": audit_metadata,
    }
    return metadata


def extract_transcript_turns(row: dict[str, Any]) -> list[dict[str, Any]]:
    turns = turns_from_structured_list(row)
    if turns:
        return turns

    transcript_text = first_string(
        row,
        "transcript",
        "transcript_text",
        "full_transcript",
        "text",
        "normalized_text",
    )
    if transcript_text:
        return turns_from_text(transcript_text)

    nested_text = find_first_text_blob(row)
    if nested_text:
        return turns_from_text(nested_text)
    return []


def turns_from_structured_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_keys = ("turns", "utterances", "segments", "dialogue", "messages", "conversation")
    for key in candidate_keys:
        value = row.get(key)
        if not isinstance(value, list):
            continue

        turns: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            text = first_string(item, "text", "utterance", "transcript", "content", "sentence")
            if not text:
                continue
            speaker = first_string(item, "speaker", "role", "channel", "participant", default=speaker_for_index(index))
            start = first_number(item, "start", "start_time", "start_ms", "timestamp")
            turns.append(
                {
                    "speaker": normalize_speaker(speaker),
                    "text": text.strip(),
                    "timestamp_seconds": normalize_timestamp(start, index),
                }
            )
        if turns:
            return turns
    return []


def turns_from_text(transcript_text: str) -> list[dict[str, Any]]:
    parts = [line.strip() for line in transcript_text.splitlines() if line.strip()]
    if not parts:
        parts = [segment.strip() for segment in transcript_text.split(".") if segment.strip()]

    turns: list[dict[str, Any]] = []
    for index, part in enumerate(parts[:200]):
        speaker, text = split_speaker_prefix(part, index)
        turns.append(
            {
                "speaker": speaker,
                "text": text,
                "timestamp_seconds": float(index * 8),
            }
        )
    return turns


def split_speaker_prefix(line: str, index: int) -> tuple[str, str]:
    for delimiter in (":", "-", "—"):
        if delimiter not in line:
            continue
        prefix, remainder = line.split(delimiter, 1)
        if 1 <= len(prefix.strip()) <= 24:
            return normalize_speaker(prefix.strip()), remainder.strip()
    return speaker_for_index(index), line.strip()


def find_first_text_blob(node: Any) -> str | None:
    if isinstance(node, dict):
        for value in node.values():
            result = find_first_text_blob(value)
            if result:
                return result
    elif isinstance(node, list):
        for value in node:
            result = find_first_text_blob(value)
            if result:
                return result
    elif isinstance(node, str) and len(node.split()) >= 5:
        return node
    return None


def first_string(node: dict[str, Any], *keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def first_number(node: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def normalize_timestamp(value: float | None, index: int) -> float:
    if value is None:
        return float(index * 8)
    if value > 10000:
        return float(value / 1000.0)
    return float(value)


def normalize_speaker(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in ("agent", "rep", "advisor", "support", "assistant", "operator")):
        return "agent"
    if any(token in lowered for token in ("customer", "caller", "client", "user", "consumer")):
        return "customer"
    return lowered.replace(" ", "_")[:32] or "agent"


def speaker_for_index(index: int) -> str:
    return "agent" if index % 2 == 0 else "customer"


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


def metadata_bool(node: dict[str, Any], key: str, default: bool = False) -> bool:
    value = node.get(key, default)
    return value if isinstance(value, bool) else default


def build_payload(sample: TranscriptSample, index: int, args: argparse.Namespace) -> dict[str, Any]:
    turns = maybe_inject_disclosure(sample.transcript_turns, args.mode)
    audit_metadata = sample.metadata.get("audit_metadata", {})
    transcript = "\n".join(f"{turn['speaker'].title()}: {turn['text']}" for turn in turns)

    source_evidence = audit_metadata.get("source_evidence")
    if not isinstance(source_evidence, dict):
        source_evidence = {}

    return {
        "call_id": f"hf-{index:05d}",
        "tenant": args.tenant,
        "deployer": args.deployer,
        "transcript": transcript,
        "agent_version": args.agent_version,
        "policy_version": args.policy_version,
        "raw_audio_uri": sample.raw_audio_uri,
        "synthetic_audio_used": metadata_bool(source_evidence, "synthetic_audio_used", args.mode == "inject-disclosure"),
        "synthetic_audio_marked": metadata_bool(source_evidence, "synthetic_audio_marked", args.mode == "inject-disclosure"),
        "deepfake_like_content_flag": metadata_bool(source_evidence, "deepfake_like_content_flag"),
        "emotion_recognition_used": metadata_bool(audit_metadata, "emotion_recognition_used"),
        "biometric_categorisation_used": metadata_bool(audit_metadata, "biometric_categorisation_used"),
        "decision_support_flag": metadata_bool(audit_metadata, "decision_support_flag"),
        "human_oversight_path_present": metadata_bool(audit_metadata, "human_oversight_path_present", True),
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


def run_audits(samples: list[TranscriptSample], args: argparse.Namespace) -> dict[str, Any]:
    disposition_counts: Counter[str] = Counter()
    article_status_counts: Counter[str] = Counter()
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

        record = response_body
        disposition_counts[str(record.get("disposition", ""))] += 1
        for finding in record.get("findings", []):
            if isinstance(finding, dict):
                article_status_counts[f'{finding.get("article", "")}:{finding.get("status", "")}'] += 1

        records.append(
            {
                "source_id": sample.source_id,
                "case_id": sample.metadata.get("case_id"),
                "scenario": sample.metadata.get("scenario"),
                "risk_type": sample.metadata.get("risk_type"),
                "expected_disposition": sample.metadata.get("expected_disposition"),
                "voice_run_id": record.get("voice_run_id"),
                "call_id": record.get("call_id"),
                "status": record.get("status"),
                "disposition": record.get("disposition"),
                "applicability": record.get("applicability"),
                "finding_count": record.get("finding_count", len(record.get("findings", []))),
            }
        )

    return {
        "api_base_url": args.api_base_url,
        "dataset": args.dataset_path or args.hf_dataset,
        "dataset_split": None if args.dataset_path else args.split,
        "mode": args.mode,
        "requested_limit": args.limit,
        "audited_records": len(records),
        "failed_records": len(failures),
        "disposition_counts": dict(disposition_counts),
        "article_status_counts": dict(article_status_counts),
        "failures": failures[:25],
        "records": records[:50],
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_summary(report: dict[str, Any], output_path: Path) -> None:
    print(f"Wrote report to {output_path}")
    print(
        f"Audited {report['audited_records']} records from {report['dataset']}"
        + (f" ({report['dataset_split']})" if report["dataset_split"] else "")
    )
    print(f"Mode: {report['mode']}")
    print("Disposition counts:")
    for key, value in sorted(report["disposition_counts"].items()):
        print(f"  {key}: {value}")
    if report["failed_records"]:
        print(f"Failures: {report['failed_records']} records could not be audited.")


def main() -> None:
    args = parse_args()
    samples = load_samples(args)
    if not samples:
        raise SystemExit("No usable transcript samples were found in the selected dataset.")

    report = run_audits(samples, args)
    output_path = Path(args.output)
    write_report(report, output_path)
    print_summary(report, output_path)


if __name__ == "__main__":
    main()
