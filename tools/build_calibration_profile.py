#!/usr/bin/env python3
"""Build the read-only calibration profile from collected stack baselines."""

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
    build_calibration_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the read-only calibration profile")
    parser.add_argument("--lab-root", type=Path, default=DEFAULT_LAB_ROOT)
    args = parser.parse_args()

    try:
        profile, _report = build_calibration_profile(lab_root=args.lab_root)
    except FactoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(args.lab_root / "baselines" / "calibration.profile.json")
    return 0 if profile.harness_overrides is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
