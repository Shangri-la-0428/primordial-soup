#!/usr/bin/env python3
"""Collect Admission Factory baseline snapshots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admission import (  # noqa: E402
    CAPTURE_LABELS,
    CAPTURE_ORIGINS,
    DEFAULT_LAB_ROOT,
    DEFAULT_PSYCHE_ROOT,
    DEFAULT_THRONGLETS_ROOT,
    FactoryError,
    collect_stack_baselines,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect stack baselines for Admission Factory v1")
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    parser.add_argument("--psyche-root", type=Path, default=DEFAULT_PSYCHE_ROOT)
    parser.add_argument("--thronglets-root", type=Path, default=DEFAULT_THRONGLETS_ROOT)
    parser.add_argument(
        "--capture-label",
        type=str,
        default="unlabeled",
        choices=CAPTURE_LABELS,
        help="Optional archive metadata label for this snapshot capture",
    )
    parser.add_argument(
        "--capture-note",
        type=str,
        default=None,
        help="Optional free-form note describing why this snapshot was captured",
    )
    parser.add_argument(
        "--capture-origin",
        type=str,
        default="manual-guided",
        choices=CAPTURE_ORIGINS,
        help="Capture origin metadata for this snapshot",
    )
    args = parser.parse_args()

    try:
        index = collect_stack_baselines(
            lab_root=args.lab_root,
            repo_root=ROOT,
            psyche_root=args.psyche_root,
            thronglets_root=args.thronglets_root,
            capture_label=args.capture_label,
            capture_note=args.capture_note,
            capture_origin=args.capture_origin,
        )
    except FactoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(args.lab_root / "baselines" / "index.json")
    return 0 if index["contract_checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
