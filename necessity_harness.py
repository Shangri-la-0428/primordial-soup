"""Evolution necessity suite facade for Primordial Soup."""

from __future__ import annotations

import argparse
from pathlib import Path

from necessity import (
    DEFAULT_NECESSITY_SCENARIOS,
    ALL_NECESSITY_SCENARIOS,
    DEFAULT_NECESSITY_CLAIMS,
    render_report,
    run_necessity_suite,
)

__all__ = [
    "ALL_NECESSITY_SCENARIOS",
    "DEFAULT_NECESSITY_CLAIMS",
    "DEFAULT_NECESSITY_SCENARIOS",
    "render_report",
    "run_necessity_suite",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evolution necessity suite")
    parser.add_argument("--scenarios", type=str, default="all")
    parser.add_argument("--seeds", type=str, default="42,7,123")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args(argv)

    scenarios = DEFAULT_NECESSITY_SCENARIOS if args.scenarios == "all" else tuple(
        part.strip() for part in args.scenarios.split(",") if part.strip()
    )
    seeds = tuple(int(part.strip()) for part in args.seeds.split(",") if part.strip())
    report = run_necessity_suite(scenarios=scenarios, seeds=seeds)
    output = report.to_json() if args.json else render_report(report)
    print(output)

    if args.output:
        Path(args.output).write_text(report.to_json(), encoding="utf-8")

    return 0 if all(result.necessity_holds for result in report.scenario_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
