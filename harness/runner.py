from __future__ import annotations

import json

from .contracts import (
    DEFAULT_SCENARIOS,
    DEFAULT_SEEDS,
    PROMOTION_METRIC_LABELS,
    CandidateDynamics,
    CandidateSummary,
    HarnessReport,
    ScenarioResult,
    boundary_contract_snapshot,
    control_candidate,
    guarded_candidate,
    validate_ontology_gate,
)
from .scenarios import SCENARIO_RUNNERS


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_avg(*values: float) -> float:
    actual = [value for value in values if value is not None]
    if not actual:
        return 0.0
    return round(sum(actual) / len(actual), 4)


def _aggregate_results(results: list[ScenarioResult]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for result in results:
        for key, value in result.metrics.items():
            if isinstance(value, bool):
                buckets.setdefault(key, []).append(1.0 if value else 0.0)
            elif isinstance(value, (int, float)) and value is not None:
                buckets.setdefault(key, []).append(float(value))

    aggregated = {key: round(sum(values) / len(values), 4) for key, values in buckets.items()}
    shock_delta = _clamp01(
        (
            aggregated.get("shock_survival_with_trace", 0.0)
            - aggregated.get("shock_survival_without_trace", 0.0)
        )
        / max(1.0, aggregated.get("shock_survival_with_trace", 1.0))
    )
    aggregated["join_gain"] = _safe_avg(
        shock_delta,
        aggregated.get("local_repair_precision", 0.0),
        aggregated.get("continuity_survival", 0.0),
    )
    aggregated["poison_resistance"] = _safe_avg(
        aggregated.get("false_signal_suppression", 0.0),
        1.0 - aggregated.get("cross_space_contamination", 0.0),
        1.0 - aggregated.get("global_contamination_rate", 0.0),
        aggregated.get("negative_feedback_trigger_rate", 0.0),
    )
    aggregated["innovation_preservation"] = _safe_avg(
        aggregated.get("reversible_probe_survival_rate", 0.0),
        1.0 - aggregated.get("stale_path_overreach_rate", 0.0),
        1.0 - aggregated.get("negative_feedback_overreach_rate", 0.0),
    )
    aggregated["capability_conflict_governance"] = _safe_avg(
        aggregated.get("mixed_residue_resolution_rate", 0.0),
        1.0 - aggregated.get("strong_model_overreach_rate", 0.0),
        1.0 - aggregated.get("weak_legacy_veto_rate", 0.0),
    )
    aggregated["new_nouns"] = 0.0
    return aggregated


def _build_control_summary(
    candidate: CandidateDynamics,
    scenario_results: list[ScenarioResult],
) -> CandidateSummary:
    metrics = _aggregate_results(scenario_results)
    return CandidateSummary(
        candidate=candidate.name,
        concept_mapping=candidate.concept_mapping,
        metrics=metrics,
        ontology_gate_failures=[],
        mechanism_gate_failures=[],
        improvements=[],
        passes_ontology_gate=True,
        passes_mechanism_gate=True,
        passes_gate=True,
    )


def compare_candidate_metrics(
    candidate_metrics: dict[str, float],
    control_metrics: dict[str, float],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    improvements: list[str] = []
    for key, label in PROMOTION_METRIC_LABELS.items():
        if candidate_metrics.get(key, 0.0) < control_metrics.get(key, 0.0):
            failures.append(f"{label} regressed against control")
        elif candidate_metrics.get(key, 0.0) > control_metrics.get(key, 0.0):
            improvements.append(label)
    return failures, improvements


def compute_metric_deltas(
    candidate_metrics: dict[str, float],
    control_metrics: dict[str, float],
) -> dict[str, float]:
    keys = set(candidate_metrics) | set(control_metrics)
    return {
        key: round(candidate_metrics.get(key, 0.0) - control_metrics.get(key, 0.0), 4)
        for key in sorted(keys)
    }


def _evaluate_candidate(
    candidate: CandidateDynamics,
    candidate_results: list[ScenarioResult],
    control_results: list[ScenarioResult],
) -> CandidateSummary:
    ontology_failures = validate_ontology_gate(candidate)
    mechanism_failures: list[str] = []
    improvements: list[str] = []

    candidate_metrics = _aggregate_results(candidate_results)
    control_metrics = _aggregate_results(control_results)
    candidate_metrics["new_nouns"] = float(len(candidate.concept_mapping.new_nouns))

    for result in candidate_results:
        if result.name == "self-collapse-and-recovery" and bool(result.metrics["undetected_irrecoverable_collapse"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} produced undetected irrecoverable collapse"
            )
        if result.name == "wrong-signal-reinforcement":
            wrong_retention = float(result.metrics["wrong_retention_turns"])
            verified_retention = float(result.metrics["verified_retention_turns"])
            if wrong_retention > verified_retention:
                mechanism_failures.append(
                    f"{result.name}: seed {result.seed} kept wrong signals longer than verified signals"
                )
        if result.name == "capability-conflict-falls-to-mixed-residue" and not bool(result.metrics["mixed_residue_engaged"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} failed to hold unresolved conflict in mixed-residue"
            )
        if result.name == "strong-prior-cannot-form-stable-path" and bool(result.metrics["strong_prior_became_stable_path"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} allowed capability prior to form a stable path"
            )
        if result.name == "weak-legacy-cannot-veto-reversible-correction" and bool(result.metrics["weak_legacy_vetoed_reversible_probe"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} let weak legacy traces veto a reversible correction"
            )
        if result.name == "old-knowledge-cannot-veto-reversible-novelty" and bool(result.metrics["stale_path_overreach"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} let old knowledge overreach onto reversible novelty"
            )
        if result.name == "repeated-local-damage-triggers-negative-feedback" and not bool(result.metrics["negative_feedback_triggered"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} failed to trigger negative feedback after repeated local damage"
            )
        if result.name == "reversible-novelty-survives-negative-feedback" and bool(result.metrics["negative_feedback_closed_reversible_probe"]):
            mechanism_failures.append(
                f"{result.name}: seed {result.seed} let negative feedback close a reversible probe"
            )

    metric_failures, metric_improvements = compare_candidate_metrics(
        candidate_metrics,
        control_metrics,
    )
    mechanism_failures.extend(metric_failures)
    improvements.extend(metric_improvements)

    if candidate_metrics.get("new_nouns", 0.0) > 0.0:
        mechanism_failures.append("candidate introduced non-zero new nouns")

    passes_ontology = not ontology_failures
    passes_mechanism = not mechanism_failures
    return CandidateSummary(
        candidate=candidate.name,
        concept_mapping=candidate.concept_mapping,
        metrics=candidate_metrics,
        ontology_gate_failures=ontology_failures,
        mechanism_gate_failures=mechanism_failures,
        improvements=improvements,
        passes_ontology_gate=passes_ontology,
        passes_mechanism_gate=passes_mechanism,
        passes_gate=passes_ontology and passes_mechanism,
    )


def run_harness(
    candidate: CandidateDynamics | None = None,
    control: CandidateDynamics | None = None,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    scenarios: tuple[str, ...] = DEFAULT_SCENARIOS,
) -> HarnessReport:
    control = control or control_candidate()
    candidate = candidate or guarded_candidate()
    selected = tuple(name for name in scenarios if name in SCENARIO_RUNNERS)

    control_results: dict[str, list[ScenarioResult]] = {name: [] for name in selected}
    candidate_results: dict[str, list[ScenarioResult]] = {name: [] for name in selected}
    all_control: list[ScenarioResult] = []
    all_candidate: list[ScenarioResult] = []

    for seed in seeds:
        for name in selected:
            runner = SCENARIO_RUNNERS[name]
            control_result = runner(seed, control)
            candidate_result = runner(seed, candidate)
            control_results[name].append(control_result)
            candidate_results[name].append(candidate_result)
            all_control.append(control_result)
            all_candidate.append(candidate_result)

    control_summary = _build_control_summary(control, all_control)
    candidate_summary = _evaluate_candidate(candidate, all_candidate, all_control)

    return HarnessReport(
        boundary_contract=boundary_contract_snapshot(),
        seeds=seeds,
        scenarios=selected,
        control=control_summary,
        candidate=candidate_summary,
        scenario_results={"control": control_results, "candidate": candidate_results},
    )


def render_report(report: HarnessReport) -> str:
    lines = [
        "Ontology-Convergent Admission Harness",
        f"  seeds: {', '.join(str(seed) for seed in report.seeds)}",
        f"  scenarios: {', '.join(report.scenarios)}",
        "",
        f"  control: {report.control.candidate}",
        f"    metrics: {json.dumps(report.control.metrics, sort_keys=True)}",
        "",
        f"  candidate: {report.candidate.candidate}",
        f"    concept mapping: carrier={report.candidate.concept_mapping.carrier}, "
        f"dimensions={','.join(report.candidate.concept_mapping.dimensions)}",
        f"    passes ontology gate: {report.candidate.passes_ontology_gate}",
        f"    passes mechanism gate: {report.candidate.passes_mechanism_gate}",
        f"    passes gate: {report.candidate.passes_gate}",
        f"    improvements: {', '.join(report.candidate.improvements) or 'none'}",
        f"    ontology failures: {', '.join(report.candidate.ontology_gate_failures) or 'none'}",
        f"    mechanism failures: {', '.join(report.candidate.mechanism_gate_failures) or 'none'}",
        f"    metrics: {json.dumps(report.candidate.metrics, sort_keys=True)}",
    ]
    return "\n".join(lines)
