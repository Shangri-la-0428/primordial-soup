#!/usr/bin/env python3
"""Run the Admission Factory candidate matrix."""

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
    run_candidate_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Admission Factory candidate matrix")
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    parser.add_argument(
        "--calibration-profile",
        type=Path,
        default=None,
        help="Optional calibration profile path. Defaults to lab/baselines/calibration.profile.json",
    )
    parser.add_argument(
        "--replay-bundle",
        type=Path,
        default=None,
        help="Optional replay bundle path. Defaults to lab/replay/replay.bundle.json",
    )
    parser.add_argument(
        "--corpus-status",
        type=Path,
        default=None,
        help="Optional corpus status path. Defaults to lab/replay/corpus.status.json",
    )
    args = parser.parse_args()

    try:
        manifest = run_candidate_matrix(
            lab_root=args.lab_root,
            calibration_profile_path=args.calibration_profile,
            replay_bundle_path=args.replay_bundle,
            corpus_status_path=args.corpus_status,
        )
    except FactoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(args.lab_root / "results" / "promotion_manifest.json")
    return 0 if manifest.promotable_candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
