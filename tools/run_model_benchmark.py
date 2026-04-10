#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run as run_entry


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live-model Primordial Soup benchmarks")
    parser.add_argument("--model-profile", type=str, required=True)
    parser.add_argument("--transport", type=str, default=None)
    parser.add_argument("--api-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--modes", type=str, default="llm,hybrid")
    parser.add_argument("--seeds", type=str, default="42,7,123")
    parser.add_argument("--output-root", type=str, default="data/benchmarks")
    parser.add_argument("--timestamp", type=str, default=None)
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--pop", type=int, default=None)
    parser.add_argument("--print-every", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    timestamp = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    benchmark_dir = Path(args.output_root) / args.model_profile / timestamp
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    live_parser = run_entry.build_parser()
    modes = _parse_csv(args.modes)
    seeds = [int(value) for value in _parse_csv(args.seeds)]

    runs: list[dict] = []
    for mode in modes:
        if mode not in {"llm", "hybrid"}:
            parser.error("benchmark modes must be drawn from llm,hybrid")
        for seed in seeds:
            cli_args = [
                f"--{mode}",
                "--seed",
                str(seed),
                "--data-dir",
                str(benchmark_dir),
                "--model-profile",
                args.model_profile,
            ]
            if args.transport:
                cli_args.extend(["--transport", args.transport])
            if args.api_url:
                cli_args.extend(["--api-url", args.api_url])
            if args.api_key:
                cli_args.extend(["--api-key", args.api_key])
            if args.model:
                cli_args.extend(["--model", args.model])
            if args.ticks is not None:
                cli_args.extend(["--ticks", str(args.ticks)])
            if args.pop is not None:
                cli_args.extend(["--pop", str(args.pop)])
            if args.print_every is not None:
                cli_args.extend(["--print-every", str(args.print_every)])

            live_args = live_parser.parse_args(cli_args)
            run_summary = run_entry.run_live_simulation(
                live_args,
                output_name=f"{mode}_seed{seed}.json",
            )
            runs.append(run_summary)

    summary = {
        "profile_id": args.model_profile,
        "timestamp": timestamp,
        "benchmark_dir": str(benchmark_dir),
        "runs": runs,
    }
    (benchmark_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Benchmark summary saved to {benchmark_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
