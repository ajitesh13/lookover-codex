from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .runtime import RuntimeClient
from .scanner import scan_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prerun", description="Pre-run scan and publish utility for LangChain/LangGraph projects.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a project for governance evidence and runtime risks.")
    scan_parser.add_argument("project_path", help="Path to the project to scan.")
    scan_parser.add_argument("--strict", action="store_true", help="Fail on blocking governance gaps.")
    scan_parser.add_argument("--output", help="Write the scan JSON to a file.")
    scan_parser.add_argument("--backend-url", default=None, help="Backend URL for defaults and future publishing.")
    scan_parser.set_defaults(func=_cmd_scan)

    publish_parser = subparsers.add_parser("publish", help="Publish a scan JSON document to the backend.")
    publish_parser.add_argument("scan_json", help="Path to the scan JSON file.")
    publish_parser.add_argument("--backend-url", default=None, help="Backend URL to publish to.")
    publish_parser.set_defaults(func=_cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _backend_url(value: str | None) -> str:
    return value or os.environ.get("LOOKOVER_BACKEND_URL") or os.environ.get("BACKEND_URL") or "http://localhost:8080"


def _cmd_scan(args: argparse.Namespace) -> int:
    result = scan_project(args.project_path, strict=args.strict).to_dict()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload + "\n")
    if args.strict and result.get("strict_result") == "block":
        return 1
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    path = Path(args.scan_json)
    scan = json.loads(path.read_text(encoding="utf-8"))
    client = RuntimeClient(_backend_url(args.backend_url))
    response = client.post_scan(scan)
    sys.stdout.write(json.dumps(response, indent=2, sort_keys=True) + "\n")
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
