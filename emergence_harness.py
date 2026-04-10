"""Ontology-convergent admission harness facade for Primordial Soup."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness import (
    ALLOWED_EXISTING_NOUNS,
    DEFAULT_SCENARIOS,
    DEFAULT_SEEDS,
    FROZEN_DIMENSIONS,
    FROZEN_EVIDENCE_STATES,
    FROZEN_IDENTITY_PRIMITIVES,
    FROZEN_LAYER_ROLES,
    FROZEN_SHARED_CARRIERS,
    FROZEN_SIGNAL_KINDS,
    FROZEN_TRACE_TAXONOMY,
    CandidateDynamics,
    CandidateSummary,
    ConceptMapping,
    HarnessReport,
    PROMOTION_METRIC_LABELS,
    ScenarioResult,
    boundary_contract_snapshot,
    candidate_from_payload,
    compare_candidate_metrics,
    compute_metric_deltas,
    control_candidate,
    default_concept_mapping,
    guarded_candidate,
    load_candidate_from_json,
    render_report,
    run_harness,
    validate_ontology_gate,
)

__all__ = [
    "ALLOWED_EXISTING_NOUNS",
    "CandidateDynamics",
    "CandidateSummary",
    "ConceptMapping",
    "DEFAULT_SCENARIOS",
    "DEFAULT_SEEDS",
    "FROZEN_DIMENSIONS",
    "FROZEN_EVIDENCE_STATES",
    "FROZEN_IDENTITY_PRIMITIVES",
    "FROZEN_LAYER_ROLES",
    "FROZEN_SHARED_CARRIERS",
    "FROZEN_SIGNAL_KINDS",
    "FROZEN_TRACE_TAXONOMY",
    "HarnessReport",
    "PROMOTION_METRIC_LABELS",
    "ScenarioResult",
    "boundary_contract_snapshot",
    "candidate_from_payload",
    "compare_candidate_metrics",
    "compute_metric_deltas",
    "control_candidate",
    "default_concept_mapping",
    "guarded_candidate",
    "load_candidate_from_json",
    "render_report",
    "run_harness",
    "validate_ontology_gate",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ontology-convergent admission harness")
    parser.add_argument("--candidate-config", type=str, default=None)
    parser.add_argument("--scenarios", type=str, default="all")
    parser.add_argument("--seeds", type=str, default="42,7,123")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args(argv)

    candidate = load_candidate_from_json(args.candidate_config) if args.candidate_config else guarded_candidate()
    scenarios = DEFAULT_SCENARIOS if args.scenarios == "all" else tuple(
        part.strip() for part in args.scenarios.split(",") if part.strip()
    )
    seeds = tuple(int(part.strip()) for part in args.seeds.split(",") if part.strip())

    report = run_harness(candidate=candidate, seeds=seeds, scenarios=scenarios)
    output = report.to_json() if args.json else render_report(report)
    print(output)

    if args.output:
        Path(args.output).write_text(report.to_json(), encoding="utf-8")

    return 0 if report.candidate.passes_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
