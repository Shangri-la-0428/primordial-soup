#!/usr/bin/env python3
"""Build the replay bundle from archived baseline snapshots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admission import (  # noqa: E402
    DEFAULT_LAB_ROOT,
    FactoryError,
    build_replay_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the replay-calibrated bundle")
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    args = parser.parse_args()

    try:
        _bundle, _report, _status = build_replay_bundle(lab_root=args.lab_root)
    except FactoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(args.lab_root / "replay" / "replay.bundle.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
