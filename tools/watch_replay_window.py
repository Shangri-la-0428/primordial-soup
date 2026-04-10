#!/usr/bin/env python3
"""Poll the read-only stack until a replay window is protocol-supported."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admission import (  # noqa: E402
    CAPTURE_LABELS,
    DEFAULT_LAB_ROOT,
    DEFAULT_PSYCHE_ROOT,
    DEFAULT_THRONGLETS_ROOT,
    FactoryError,
    collect_stack_baselines,
    probe_stack_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch for a protocol-supported replay window")
    parser.add_argument("--label", required=True, choices=CAPTURE_LABELS[:-1])
    parser.add_argument("--attempts", type=int, default=1, help="Number of polling attempts before giving up")
    parser.add_argument("--poll-seconds", type=float, default=30.0, help="Seconds to wait between attempts")
    parser.add_argument(
        "--capture-when-ready",
        action="store_true",
        help="When the target label becomes protocol-supported, archive a labeled baseline snapshot",
    )
    parser.add_argument(
        "--note",
        type=str,
        default=None,
        help="Required capture note when --capture-when-ready is set",
    )
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    parser.add_argument("--psyche-root", type=Path, default=DEFAULT_PSYCHE_ROOT)
    parser.add_argument("--thronglets-root", type=Path, default=DEFAULT_THRONGLETS_ROOT)
    args = parser.parse_args()

    if args.capture_when_ready and not (args.note or "").strip():
        parser.error("--note is required when --capture-when-ready is set")
    if args.attempts < 1:
        parser.error("--attempts must be >= 1")
    if args.poll_seconds < 0:
        parser.error("--poll-seconds must be >= 0")

    last_report: dict | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            report = probe_stack_state(
                repo_root=ROOT,
                psyche_root=args.psyche_root,
                thronglets_root=args.thronglets_root,
                capture_label=args.label,
            )
        except FactoryError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        payload = {
            "attempt": attempt,
            "label": args.label,
            "captured_at": report["captured_at"],
            "supported": report["protocol_eval"]["selected_label_supported"],
            "recommended_labels": report["protocol_eval"]["recommended_labels"],
            "blocking_reasons": report["protocol_eval"]["blocking_reasons"],
            "contract_checks": report["contract_checks"],
            "stack_signals": report["stack_signals"],
        }
        print(json.dumps(payload, indent=2))
        last_report = payload

        if payload["supported"]:
            if args.capture_when_ready:
                try:
                    collect_stack_baselines(
                        lab_root=args.lab_root,
                        repo_root=ROOT,
                        psyche_root=args.psyche_root,
                        thronglets_root=args.thronglets_root,
                        capture_label=args.label,
                        capture_note=args.note,
                        capture_origin="manual-guided",
                    )
                except FactoryError as exc:
                    print(str(exc), file=sys.stderr)
                    return 1
                print(args.lab_root / "baselines" / "index.json")
            return 0

        if attempt < args.attempts and args.poll_seconds:
            time.sleep(args.poll_seconds)

    if last_report is None:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
