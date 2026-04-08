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

from soup import Simulation, SimConfig, LLMEngine, LLMConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Primordial Soup evolution simulation")
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--pop", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=30)
    parser.add_argument("--height", type=int, default=30)
    parser.add_argument("--resource-rate", type=float, default=0.02)
    parser.add_argument("--mutation", type=float, default=0.05)
    parser.add_argument("--print-every", type=int, default=None)

    # Engine mode
    parser.add_argument("--llm", action="store_true", help="LLM-only mode")
    parser.add_argument("--hybrid", action="store_true", help="50/50 Rule+LLM competition")
    parser.add_argument("--neural", action="store_true", help="Neural genome evolution")
    parser.add_argument("--api-url", type=str,
                        default="https://api.lkeap.cloud.tencent.com/plan/anthropic/v1/messages")
    parser.add_argument("--api-key", type=str,
                        default="sk-tp-hHhOjXUZBMmhuueLlVuXYTZBBgBkE9r8PEA3JSJzgiit5XWS")
    parser.add_argument("--model", type=str, default="kimi-k2.5")

    # Ablation
    parser.add_argument("--no-psyche", action="store_true",
                        help="Ablation: fix Psyche at baseline, no decay/coupling/stimulus")

    # Environmental shocks
    parser.add_argument("--shock", type=str, action="append", default=[],
                        help="TICK:TYPE — e.g. 500:famine or 500:famine+wipe (types: relocate, famine, wipe_traces, famine+wipe)")
    args = parser.parse_args()

    use_llm = args.llm or args.hybrid

    # Sensible defaults per mode
    if args.neural:
        ticks = args.ticks or 1000
        pop = args.pop or 50
        print_every = args.print_every or 50
        if args.mutation == 0.05:  # default — override for neural
            args.mutation = 0.02
    elif use_llm:
        ticks = args.ticks or 200
        pop = args.pop or 20
        print_every = args.print_every or 20
    else:
        ticks = args.ticks or 1000
        pop = args.pop or 50
        print_every = args.print_every or 50

    config = SimConfig(
        width=args.width,
        height=args.height,
        resource_rate=args.resource_rate,
        initial_population=pop,
        mutation_sigma=args.mutation,
        ticks=ticks,
        print_every=print_every,
        seed=args.seed,
        ablate_psyche=args.no_psyche,
    )

    sim = Simulation(config)

    # Register shocks
    for spec in args.shock:
        if ":" in spec:
            tick_str, stype = spec.split(":", 1)
            sim.shocks[int(tick_str)] = stype
        else:
            sim.shocks[int(spec)] = "famine"  # default shock type

    if use_llm:
        llm_config = LLMConfig(
            api_url=args.api_url,
            api_key=args.api_key,
            model=args.model,
            max_workers=min(pop * 2, 40),
        )
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

    sim.run()


if __name__ == "__main__":
    main()
