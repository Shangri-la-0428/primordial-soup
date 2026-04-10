#!/usr/bin/env python3
"""Collect a labeled replay window snapshot."""

from __future__ import annotations

import argparse
import sys
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
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a labeled replay corpus snapshot")
    parser.add_argument("--label", required=True, choices=CAPTURE_LABELS[:-1])
    parser.add_argument(
        "--note",
        type=str,
        required=True,
        help="Required note explaining why this labeled replay window was captured",
    )
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    parser.add_argument("--psyche-root", type=Path, default=DEFAULT_PSYCHE_ROOT)
    parser.add_argument("--thronglets-root", type=Path, default=DEFAULT_THRONGLETS_ROOT)
    args = parser.parse_args()

    try:
        index = collect_stack_baselines(
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
    return 0 if index["contract_checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
