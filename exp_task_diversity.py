"""Experiment: Task Diversity vs Stigmergic Accumulation.

Tests whether splitting resources into K distinct "kinds" (signals only
reinforce within-kind) fragments stigmergic emergence. This is the soup
analog of: "single Thronglets user working across 7+ projects vs a
specialist repeating similar tasks."

Arms:
  K=1  — baseline, single resource kind (replicates Exp 4 conditions)
  K=3  — moderate fragmentation
  K=5  — high fragmentation

Metrics per run:
  - max_reinforcement (across all signals): depth of best trace
  - trace_count (signals with reinforcements >= 10): number of stable traces
  - signal_count_total: total signals alive at end
  - signal_gene_mean: agent genome convergence on signaling
  - population_final / births_total / deaths_total: biological fitness
  - per_kind_max_reinforcement: did ALL kinds accumulate or only some?

Usage:
  python3 exp_task_diversity.py                     # runs rule engine, 3 seeds × 3 arms
  python3 exp_task_diversity.py --ticks 500         # custom tick count
  python3 exp_task_diversity.py --llm               # use kimi LLM agents
  python3 exp_task_diversity.py --pop 30            # smaller pop (useful for LLM)
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from soup import Simulation, SimConfig, LLMEngine
from model_lane import resolve_llm_config


DEFAULT_ARMS = [1, 3, 5]
DEFAULT_SEEDS = [42, 7, 123]


def run_one(seed: int, K: int, *, ticks: int, pop: int, llm_config=None,
            data_dir: str = "data/task_diversity") -> dict:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    mode = "llm" if llm_config else "rule"
    output_name = f"{mode}_K{K}_seed{seed}.json"
    cfg = SimConfig(
        ticks=ticks,
        initial_population=pop,
        seed=seed,
        signal_kind_count=K,
        data_dir=data_dir,
        mode_name=mode,
        output_name=output_name,
        print_every=max(ticks // 4, 50),
    )
    sim = Simulation(cfg)
    if llm_config is not None:
        sim.llm_engine = LLMEngine(llm_config)
        sim.seed(pop, brain="llm")
    else:
        sim.seed(pop, brain="rule")

    t0 = time.time()
    sim.run()
    elapsed = time.time() - t0

    alive_cells = [c for c in sim.cells.values() if c.alive]
    signals = sim.env.signals
    max_r = max((s.reinforcements for s in signals), default=0)
    trace_count = sum(1 for s in signals if s.reinforcements >= 10)
    strong_trace_count = sum(1 for s in signals if s.reinforcements >= 50)

    kind_counts = Counter(s.kind for s in signals)
    kind_max_reinforcement: dict[str, int] = {}
    for s in signals:
        if s.reinforcements > kind_max_reinforcement.get(s.kind, 0):
            kind_max_reinforcement[s.kind] = s.reinforcements

    # Genome statistics (only meaningful for Genome, not NeuralGenome)
    signal_gene_mean = signal_gene_sd = None
    coop_gene_mean = apt_gene_mean = None
    if alive_cells and hasattr(alive_cells[0].genome, "signal_frequency"):
        sig_vals = [c.genome.signal_frequency for c in alive_cells]
        coop_vals = [c.genome.cooperation_bias for c in alive_cells]
        apt_vals = [c.genome.aptitude for c in alive_cells]
        signal_gene_mean = statistics.mean(sig_vals)
        signal_gene_sd = statistics.stdev(sig_vals) if len(sig_vals) > 1 else 0.0
        coop_gene_mean = statistics.mean(coop_vals)
        apt_gene_mean = statistics.mean(apt_vals)

    hist = sim.observer.history
    total_births = sum(h.births for h in hist)
    total_deaths = sum(h.deaths for h in hist)

    return {
        "seed": seed,
        "K": K,
        "mode": mode,
        "ticks": ticks,
        "pop_final": len(alive_cells),
        "births_total": total_births,
        "deaths_total": total_deaths,
        "signals_total": len(signals),
        "max_reinforcement": max_r,
        "trace_count_10": trace_count,
        "trace_count_50": strong_trace_count,
        "kind_counts": dict(kind_counts),
        "kind_max_reinforcement": kind_max_reinforcement,
        "signal_gene_mean": signal_gene_mean,
        "signal_gene_sd": signal_gene_sd,
        "coop_gene_mean": coop_gene_mean,
        "apt_gene_mean": apt_gene_mean,
        "elapsed_sec": round(elapsed, 1),
    }


def aggregate(results: list[dict]) -> dict:
    by_K: dict[int, list[dict]] = {}
    for r in results:
        by_K.setdefault(r["K"], []).append(r)

    summary = {}
    for K, rows in sorted(by_K.items()):
        summary[K] = {
            "n_runs": len(rows),
            "max_reinforcement_mean": statistics.mean(r["max_reinforcement"] for r in rows),
            "max_reinforcement_sd": statistics.stdev([r["max_reinforcement"] for r in rows]) if len(rows) > 1 else 0.0,
            "trace_count_10_mean": statistics.mean(r["trace_count_10"] for r in rows),
            "trace_count_50_mean": statistics.mean(r["trace_count_50"] for r in rows),
            "signals_total_mean": statistics.mean(r["signals_total"] for r in rows),
            "pop_final_mean": statistics.mean(r["pop_final"] for r in rows),
            "signal_gene_mean": (
                statistics.mean([r["signal_gene_mean"] for r in rows if r["signal_gene_mean"] is not None])
                if any(r["signal_gene_mean"] is not None for r in rows) else None
            ),
            "coop_gene_mean": (
                statistics.mean([r["coop_gene_mean"] for r in rows if r["coop_gene_mean"] is not None])
                if any(r["coop_gene_mean"] is not None for r in rows) else None
            ),
            "apt_gene_mean": (
                statistics.mean([r["apt_gene_mean"] for r in rows if r["apt_gene_mean"] is not None])
                if any(r["apt_gene_mean"] is not None for r in rows) else None
            ),
        }
    return summary


def print_table(summary: dict) -> None:
    print()
    print("=" * 78)
    print(f"  {'K':<3} {'max_reinf':<14} {'traces(≥10)':<13} {'traces(≥50)':<13} {'signals':<10} {'sig_gene':<10}")
    print("-" * 78)
    for K, s in summary.items():
        mr = f"{s['max_reinforcement_mean']:.0f}±{s['max_reinforcement_sd']:.0f}"
        tr10 = f"{s['trace_count_10_mean']:.1f}"
        tr50 = f"{s['trace_count_50_mean']:.1f}"
        sig = f"{s['signals_total_mean']:.0f}"
        sg = f"{s['signal_gene_mean']:.2f}" if s['signal_gene_mean'] is not None else "—"
        print(f"  {K:<3} {mr:<14} {tr10:<13} {tr50:<13} {sig:<10} {sg:<10}")
    print("=" * 78)

    # Baseline → fragmented deltas
    if 1 in summary and 5 in summary:
        b = summary[1]
        h = summary[5]
        dmr = (h["max_reinforcement_mean"] - b["max_reinforcement_mean"]) / max(b["max_reinforcement_mean"], 1) * 100
        dtr = (h["trace_count_10_mean"] - b["trace_count_10_mean"]) / max(b["trace_count_10_mean"], 1) * 100
        print(f"\n  K=1 → K=5: max_reinforcement {dmr:+.0f}%, trace_count_10 {dtr:+.0f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=500)
    parser.add_argument("--pop", type=int, default=50)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--arms", type=int, nargs="+", default=DEFAULT_ARMS,
                        help="K values to test (default: 1 3 5)")
    parser.add_argument("--llm", action="store_true", help="use LLM (kimi) agents")
    parser.add_argument("--model-profile", default="kimi")
    parser.add_argument("--output", default="data/task_diversity/summary.json")
    args = parser.parse_args()

    llm_config = None
    if args.llm:
        llm_config = resolve_llm_config(profile_id=args.model_profile)
        if args.pop > 25:
            print(f"  [llm] reducing pop {args.pop} → 20 to save API calls")
            args.pop = 20
        print(f"  [llm] profile={args.model_profile} model={llm_config.model}")

    results = []
    for K in args.arms:
        for seed in args.seeds:
            print(f"\n### K={K} seed={seed} ticks={args.ticks} pop={args.pop} mode={'llm' if args.llm else 'rule'} ###")
            row = run_one(seed, K, ticks=args.ticks, pop=args.pop, llm_config=llm_config)
            results.append(row)
            print(f"   → max_reinf={row['max_reinforcement']} trace≥10={row['trace_count_10']} "
                  f"signals={row['signals_total']} sig_gene={row['signal_gene_mean']} "
                  f"elapsed={row['elapsed_sec']}s")

    summary = aggregate(results)
    print_table(summary)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "args": vars(args),
        "results": results,
        "summary": summary,
    }, indent=2))
    print(f"\n  saved to {out_path}")


if __name__ == "__main__":
    main()
