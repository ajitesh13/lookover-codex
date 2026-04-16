from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "run_hf_dataset_audit.py"
SPEC = importlib.util.spec_from_file_location("hf_dataset_audit_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_build_sample_handles_structured_transcript():
    row = {
        "audio_url": "https://example.com/audio.wav",
        "segments": [
            {"speaker": "Agent", "text": "Hello there", "start": 0},
            {"speaker": "Customer", "text": "I need help", "start": 4.5},
        ],
    }

    sample = MODULE.build_sample(row, source_id="demo:0")

    assert sample is not None
    assert sample.raw_audio_uri == "https://example.com/audio.wav"
    assert sample.transcript_turns == [
        {"speaker": "agent", "text": "Hello there", "timestamp_seconds": 0.0},
        {"speaker": "customer", "text": "I need help", "timestamp_seconds": 4.5},
    ]


def test_local_dataset_flow_writes_report(tmp_path: Path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "transcript": "Agent: Thank you for calling.\nCustomer: I have a billing issue.",
                    "audio_path": "file:///demo.wav",
                }
            ]
        ),
        encoding="utf-8",
    )
    namespace = type(
        "Args",
        (),
        {
            "dataset_path": str(dataset_path),
            "hf_dataset": MODULE.DEFAULT_DATASET_ID,
            "split": "train",
            "limit": 1,
            "offset": 0,
            "seed": 7,
            "mode": "inject-disclosure",
            "tenant": "hf-test",
            "deployer": "voice-ops",
            "agent_version": "hf-replay-v1",
            "policy_version": "policy-hf-replay",
            "output": str(tmp_path / "report.json"),
        },
    )()

    samples = MODULE.load_samples(namespace)
    report = MODULE.run_audits(samples, namespace)
    MODULE.write_report(report, Path(namespace.output))

    written = json.loads(Path(namespace.output).read_text(encoding="utf-8"))
    assert written["audited_records"] == 1
    assert written["failed_records"] == 0
    assert written["disposition_counts"]


def test_local_dataset_metadata_overrides_affect_audit(tmp_path: Path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "synthetic-1",
                    "risk_type": "synthetic_voice_unmarked",
                    "scenario": "Synthetic voice without provenance marker.",
                    "expected_disposition": "hard_fail",
                    "turns": [
                        {"speaker": "agent", "text": "This is your automated helper from [ORGANIZATION].", "start": 0},
                        {"speaker": "customer", "text": "Are you a recording?", "start": 9},
                    ],
                    "audit_metadata": {
                        "source_evidence": {
                            "synthetic_audio_used": True,
                            "synthetic_audio_marked": False,
                            "deepfake_like_content_flag": True,
                        }
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    namespace = type(
        "Args",
        (),
        {
            "dataset_path": str(dataset_path),
            "hf_dataset": MODULE.DEFAULT_DATASET_ID,
            "split": "train",
            "limit": 1,
            "offset": 0,
            "seed": 7,
            "mode": "baseline",
            "tenant": "hf-test",
            "deployer": "voice-ops",
            "agent_version": "hf-replay-v1",
            "policy_version": "policy-hf-replay",
            "output": str(tmp_path / "report.json"),
        },
    )()

    samples = MODULE.load_samples(namespace)
    report = MODULE.run_audits(samples, namespace)

    assert report["audited_records"] == 1
    assert report["disposition_counts"] == {"hard_fail": 1}
    assert report["records"][0]["risk_type"] == "synthetic_voice_unmarked"
