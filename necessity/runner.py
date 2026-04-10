from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .contracts import (
    DEFAULT_NECESSITY_CLAIMS,
    DEFAULT_NECESSITY_SCENARIOS,
    DEFAULT_NECESSITY_SEEDS,
    NECESSITY_STACKS,
    NecessityClaim,
    NecessityReport,
    NecessityScenarioResult,
)
from .scenarios import SCENARIO_RUNNERS


CLAIM_SCENARIOS = {
    "C1": "regime-shift",
    "C2": "memory-timescale-split",
    "C3": "memory-timescale-split",
    "C4": "heterogeneous-brains",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _average_metrics(samples: list[dict[str, float]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        for key, value in sample.items():
            buckets[key].append(float(value))
    return {key: round(sum(values) / len(values), 4) for key, values in sorted(buckets.items())}


def evaluate_scenario(
    scenario: str,
    *,
    stack_name: str,
    seeds: tuple[int, ...] = DEFAULT_NECESSITY_SEEDS,
) -> dict[str, float]:
    stack = NECESSITY_STACKS[stack_name]
    runner = SCENARIO_RUNNERS[scenario]
    return _average_metrics([runner(seed, stack) for seed in seeds])


def evaluate_claim_outcome(
    claim: NecessityClaim,
    *,
    scenario: str,
    control_metrics: dict[str, float],
    open_metrics: dict[str, float],
) -> bool:
    if claim.id == "C1":
        return (
            open_metrics["adaptation_lag"] <= control_metrics["adaptation_lag"] - 2.0
            and open_metrics["post_shift_survival"] >= control_metrics["post_shift_survival"] + 0.15
            and open_metrics["recovery_slope"] >= control_metrics["recovery_slope"] + 0.10
        )
    if claim.id == "C2":
        return (
            open_metrics["memory_leverage"] >= control_metrics["memory_leverage"] + 0.18
            and open_metrics["post_shift_survival"] >= control_metrics["post_shift_survival"] + 0.06
        )
    if claim.id == "C3":
        return (
            open_metrics["recovery_slope"] >= control_metrics["recovery_slope"] + 0.08
            and open_metrics["adaptation_lag"] <= control_metrics["adaptation_lag"] - 0.75
        )
    if claim.id == "C4":
        return (
            open_metrics["heterogeneity_absorption"] >= control_metrics["heterogeneity_absorption"] + 0.20
            and open_metrics["organization_advantage"] >= control_metrics["organization_advantage"] + 0.10
            and open_metrics["post_shift_survival"] >= control_metrics["post_shift_survival"]
        )
    raise ValueError(f"unknown necessity claim: {claim.id}")


def run_necessity_suite(
    *,
    claims: Iterable[NecessityClaim] = DEFAULT_NECESSITY_CLAIMS,
    scenarios: tuple[str, ...] = DEFAULT_NECESSITY_SCENARIOS,
    seeds: tuple[int, ...] = DEFAULT_NECESSITY_SEEDS,
) -> NecessityReport:
    selected_scenarios = set(scenarios)
    claim_list = [claim for claim in claims if CLAIM_SCENARIOS[claim.id] in selected_scenarios]
    scenario_results: list[NecessityScenarioResult] = []
    conclusions: list[str] = []

    for claim in claim_list:
        scenario = CLAIM_SCENARIOS[claim.id]
        control_metrics = evaluate_scenario(
            scenario,
            stack_name=claim.control_stack,
            seeds=seeds,
        )
        open_metrics = evaluate_scenario(
            scenario,
            stack_name=claim.open_stack,
            seeds=seeds,
        )
        necessity_holds = evaluate_claim_outcome(
            claim,
            scenario=scenario,
            control_metrics=control_metrics,
            open_metrics=open_metrics,
        )
        scenario_results.append(
            NecessityScenarioResult(
                claim_id=claim.id,
                scenario=scenario,
                control_metrics=control_metrics,
                open_metrics=open_metrics,
                necessity_holds=necessity_holds,
            )
        )
        if necessity_holds:
            conclusions.append(f"{claim.id} holds under {scenario}")
        else:
            conclusions.append(f"{claim.id} does not yet hold under {scenario}")

    return NecessityReport(
        generated_at=_utc_now(),
        claims=claim_list,
        scenario_results=scenario_results,
        conclusions=conclusions,
    )


def render_report(report: NecessityReport) -> str:
    lines = [
        "Evolution Necessity Suite",
        f"  claims: {', '.join(claim.id for claim in report.claims)}",
        "",
    ]
    for result in report.scenario_results:
        lines.append(f"  {result.claim_id} @ {result.scenario}")
        lines.append(f"    necessity holds: {result.necessity_holds}")
        lines.append(f"    control: {result.control_metrics}")
        lines.append(f"    open:    {result.open_metrics}")
        lines.append("")
    lines.append("  conclusions:")
    lines.extend([f"    - {item}" for item in report.conclusions])
    return "\n".join(lines)
