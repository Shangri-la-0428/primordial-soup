#!/usr/bin/env python3
"""Print the replay corpus status and protocol mismatches for the current lab."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admission import (  # noqa: E402
    DEFAULT_LAB_ROOT,
    FactoryError,
    REPLAY_FILES,
    build_replay_bundle,
    load_corpus_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show replay corpus readiness and missing labels")
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild replay bundle/status from archived snapshots before printing status",
    )
    args = parser.parse_args()

    status_path = args.lab_root / "replay" / REPLAY_FILES["status"]
    try:
        if args.refresh or not status_path.exists():
            build_replay_bundle(lab_root=args.lab_root)
        status = load_corpus_status(status_path)
    except FactoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(asdict(status), indent=2))
    return 0 if status.replay_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
