#!/usr/bin/env python3
"""Primordial Soup — entry point.

Usage:
    python run.py                         # RuleEngine only, 50 cells, 1000 ticks
    python run.py --llm                   # LLM only, 20 cells, 200 ticks
    python run.py --hybrid                # 50/50 mixed, 200 ticks — competition!
    python run.py --shock 500             # resource relocate at tick 500
    python run.py --shock 500 --shock 750 # multiple shocks
"""

import argparse
import random
from dataclasses import replace
from pathlib import Path
from typing import Any
import json

from harness import (
    DEFAULT_SCENARIOS,
    DEFAULT_SEEDS,
    load_candidate_from_json,
    render_report as render_harness_report,
    run_harness,
)
from model_lane import LLMConfig, check_model_profile, list_model_profiles, resolve_llm_config
from necessity import (
    ALL_NECESSITY_SCENARIOS,
    DEFAULT_NECESSITY_SCENARIOS,
    DEFAULT_NECESSITY_SEEDS,
    render_report as render_necessity_report,
    run_necessity_suite,
)
from soup import Simulation, SimConfig, LLMEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Primordial Soup evolution simulation")
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--pop", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=30)
    parser.add_argument("--height", type=int, default=30)
    parser.add_argument("--resource-rate", type=float, default=0.02)
    parser.add_argument("--mutation", type=float, default=0.05)
    parser.add_argument("--print-every", type=int, default=None)
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument(
        "--harness",
        action="store_true",
        help="Run the ontology-convergent admission harness instead of the live simulation",
    )
    parser.add_argument(
        "--candidate-config",
        type=str,
        default=None,
        help="JSON file overriding guarded-emergence-v2 candidate dynamics",
    )
    parser.add_argument(
        "--harness-scenarios",
        type=str,
        default="all",
        help="Comma-separated harness scenario names, or 'all'",
    )
    parser.add_argument(
        "--harness-seeds",
        type=str,
        default="42,7,123",
        help="Comma-separated harness seeds",
    )
    parser.add_argument(
        "--harness-json",
        action="store_true",
        help="Emit harness output as JSON",
    )
    parser.add_argument(
        "--harness-output",
        type=str,
        default=None,
        help="Optional path to write the JSON harness report",
    )
    parser.add_argument(
        "--necessity",
        action="store_true",
        help="Run the evolution necessity suite instead of the live simulation",
    )
    parser.add_argument(
        "--necessity-scenarios",
        type=str,
        default="all",
        help=(
            "Comma-separated necessity scenario names "
            f"({', '.join(ALL_NECESSITY_SCENARIOS)}), or 'all'"
        ),
    )
    parser.add_argument(
        "--necessity-seeds",
        type=str,
        default="42,7,123",
        help="Comma-separated necessity suite seeds",
    )
    parser.add_argument(
        "--necessity-json",
        action="store_true",
        help="Emit necessity suite output as JSON",
    )
    parser.add_argument(
        "--necessity-output",
        type=str,
        default=None,
        help="Optional path to write the JSON necessity report",
    )

    # Engine mode
    parser.add_argument("--llm", action="store_true", help="LLM-only mode")
    parser.add_argument("--hybrid", action="store_true", help="50/50 Rule+LLM competition")
    parser.add_argument("--neural", action="store_true", help="Neural genome evolution")
    parser.add_argument(
        "--model-profile",
        type=str,
        default=None,
        help="Named live-model profile (for example: kimi, anthropic-compatible, openai-compatible)",
    )
    parser.add_argument(
        "--list-model-profiles",
        action="store_true",
        help="List configured live-model profiles and exit",
    )
    parser.add_argument(
        "--check-model-profile",
        type=str,
        default=None,
        help="Check whether a named live-model profile is locally ready in the current environment and exit",
    )
    parser.add_argument(
        "--transport",
        type=str,
        default=None,
        help="Advanced override for the provider transport (anthropic_messages or openai_chat_completions)",
    )
    parser.add_argument("--api-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)

    # Ablation
    parser.add_argument(
        "--no-psyche",
        action="store_true",
        help="Ablation: fix Psyche at baseline, no decay/coupling/stimulus",
    )

    # Environmental shocks
    parser.add_argument(
        "--shock",
        type=str,
        action="append",
        default=[],
        help="TICK:TYPE — e.g. 500:famine or 500:famine+wipe (types: relocate, famine, wipe_traces, famine+wipe)",
    )
    return parser


def _mode_name(args: argparse.Namespace) -> str:
    if args.hybrid:
        return "hybrid"
    if args.llm:
        return "llm"
    if args.neural:
        return "neural"
    return "rule"


def _live_mode_defaults(args: argparse.Namespace) -> tuple[int, int, int, float]:
    use_llm = args.llm or args.hybrid
    mutation = args.mutation
    if args.neural:
        ticks = args.ticks or 1000
        pop = args.pop or 50
        print_every = args.print_every or 50
        if mutation == 0.05:
            mutation = 0.02
    elif use_llm:
        ticks = args.ticks or 200
        pop = args.pop or 20
        print_every = args.print_every or 20
    else:
        ticks = args.ticks or 1000
        pop = args.pop or 50
        print_every = args.print_every or 50
    return ticks, pop, print_every, mutation


def build_simulation(
    args: argparse.Namespace,
    *,
    output_name: str | None = None,
) -> tuple[Simulation, str, LLMConfig | None]:
    use_llm = args.llm or args.hybrid
    mode_name = _mode_name(args)
    ticks, pop, print_every, mutation = _live_mode_defaults(args)

    config = SimConfig(
        width=args.width,
        height=args.height,
        resource_rate=args.resource_rate,
        initial_population=pop,
        mutation_sigma=mutation,
        ticks=ticks,
        print_every=print_every,
        seed=args.seed,
        data_dir=args.data_dir,
        mode_name=mode_name,
        output_name=output_name,
        ablate_psyche=args.no_psyche,
    )

    sim = Simulation(config)

    for spec in args.shock:
        if ":" in spec:
            tick_str, stype = spec.split(":", 1)
            sim.shocks[int(tick_str)] = stype
        else:
            sim.shocks[int(spec)] = "famine"

    llm_config: LLMConfig | None = None
    if use_llm:
        llm_config = resolve_llm_config(
            profile_id=args.model_profile,
            transport=args.transport,
            api_url=args.api_url,
            api_key=args.api_key,
            model=args.model,
        )
        llm_config = replace(llm_config, max_workers=min(pop * 2, llm_config.max_workers))
        sim.llm_engine = LLMEngine(llm_config)

    if args.hybrid:
        random.seed(config.seed)
        half = pop // 2
        sim.seed(half, brain="rule")
        sim.seed(pop - half, brain="llm")
    elif args.llm:
        random.seed(config.seed)
        sim.seed(pop, brain="llm")
    elif args.neural:
        random.seed(config.seed)
        sim.seed(pop, brain="neural")

    return sim, mode_name, llm_config


def summarize_simulation(
    sim: Simulation,
    *,
    mode_name: str,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    if not sim.observer.history:
        return {
            "mode": mode_name,
            "seed": sim.config.seed,
            "history_path": str(
                Path(sim.config.data_dir)
                / (sim.config.output_name or f"run_{mode_name}_seed{sim.config.seed}.json")
            ),
            "profile": llm_config.metadata() if llm_config else None,
            "final_population": 0,
            "total_births": 0,
            "total_deaths": 0,
            "action_distribution": {},
            "brain_counts": {},
            "llm_stats": sim.llm_engine.stats() if sim.llm_engine else {},
        }

    last = sim.observer.history[-1]
    totals: dict[str, int] = {}
    for snap in sim.observer.history:
        for action, count in snap.action_counts.items():
            totals[action] = totals.get(action, 0) + count
    total_actions = sum(totals.values()) or 1
    action_distribution = {
        action: count / total_actions for action, count in sorted(totals.items())
    }

    return {
        "mode": mode_name,
        "seed": sim.config.seed,
        "history_path": str(
            Path(sim.config.data_dir)
            / (sim.config.output_name or f"run_{mode_name}_seed{sim.config.seed}.json")
        ),
        "profile": llm_config.metadata() if llm_config else None,
        "final_population": last.population,
        "total_births": sum(snap.births for snap in sim.observer.history),
        "total_deaths": sum(snap.deaths for snap in sim.observer.history),
        "action_distribution": action_distribution,
        "brain_counts": last.brain_counts,
        "llm_stats": sim.llm_engine.stats() if sim.llm_engine else {},
    }


def run_live_simulation(
    args: argparse.Namespace,
    *,
    output_name: str | None = None,
) -> dict[str, Any]:
    sim, mode_name, llm_config = build_simulation(args, output_name=output_name)
    sim.run()
    return summarize_simulation(sim, mode_name=mode_name, llm_config=llm_config)

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_model_profiles:
        print(json.dumps(list_model_profiles(), indent=2))
        return 0

    if args.check_model_profile:
        report = check_model_profile(args.check_model_profile)
        print(json.dumps(report, indent=2))
        return 0 if report["ready"] else 1

    if args.harness:
        candidate = (
            load_candidate_from_json(args.candidate_config)
            if args.candidate_config
            else None
        )
        scenarios = (
            DEFAULT_SCENARIOS
            if args.harness_scenarios == "all"
            else tuple(
                part.strip()
                for part in args.harness_scenarios.split(",")
                if part.strip()
            )
        )
        seeds = tuple(
            int(part.strip()) for part in args.harness_seeds.split(",") if part.strip()
        ) or DEFAULT_SEEDS
        report = run_harness(candidate=candidate, seeds=seeds, scenarios=scenarios)
        if args.harness_json:
            print(report.to_json())
        else:
            print(render_harness_report(report))
        if args.harness_output:
            Path(args.harness_output).write_text(report.to_json(), encoding="utf-8")
        return 0 if report.candidate.passes_gate else 1

    if args.necessity:
        scenarios = (
            DEFAULT_NECESSITY_SCENARIOS
            if args.necessity_scenarios == "all"
            else tuple(
                part.strip()
                for part in args.necessity_scenarios.split(",")
                if part.strip()
            )
        )
        seeds = tuple(
            int(part.strip())
            for part in args.necessity_seeds.split(",")
            if part.strip()
        ) or DEFAULT_NECESSITY_SEEDS
        report = run_necessity_suite(scenarios=scenarios, seeds=seeds)
        if args.necessity_json:
            print(report.to_json())
        else:
            print(render_necessity_report(report))
        if args.necessity_output:
            Path(args.necessity_output).write_text(report.to_json(), encoding="utf-8")
        return 0 if all(result.necessity_holds for result in report.scenario_results) else 1

    try:
        run_live_simulation(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
