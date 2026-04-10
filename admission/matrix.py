"""Candidate spec loading and promotion matrix orchestration."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from harness import (
    DEFAULT_SCENARIOS,
    DEFAULT_SEEDS,
    ConceptMapping,
    candidate_from_payload,
    compare_candidate_metrics,
    compute_metric_deltas,
    control_candidate,
    run_harness,
    validate_ontology_gate,
)

from .artifacts import (
    BASELINE_FILES,
    DEFAULT_LAB_ROOT,
    REPLAY_FILES,
    CandidateResult,
    CandidateSpec,
    FactoryError,
    PromotionManifest,
    candidate_result_path,
    ensure_lab_layout,
    load_calibration_profile,
    load_calibration_report,
    load_corpus_status,
    load_replay_bundle,
    path_ref,
    read_json,
    write_json,
    utc_now,
)
from .calibration import apply_calibration_overrides


def load_candidate_spec(path: Path) -> CandidateSpec:
    payload = read_json(path)
    required = ("id", "summary", "concept_mapping", "overrides")
    missing = [key for key in required if key not in payload]
    if missing:
        raise FactoryError(f"candidate spec {path} missing required keys: {', '.join(missing)}")

    concept_mapping = payload["concept_mapping"]
    if not isinstance(concept_mapping, dict):
        raise FactoryError(f"candidate spec {path} concept_mapping must be an object")
    if isinstance(concept_mapping.get("dimensions"), list):
        concept_mapping["dimensions"] = tuple(concept_mapping["dimensions"])
    if isinstance(concept_mapping.get("new_nouns"), list):
        concept_mapping["new_nouns"] = tuple(concept_mapping["new_nouns"])

    overrides = payload["overrides"]
    if not isinstance(overrides, dict):
        raise FactoryError(f"candidate spec {path} overrides must be an object")

    return CandidateSpec(
        id=payload["id"],
        summary=payload["summary"],
        concept_mapping=ConceptMapping(**concept_mapping),
        overrides=overrides,
        schema_version=int(payload.get("schema_version", 1)),
    )


def candidate_spec_to_dynamics(spec: CandidateSpec):
    return candidate_from_payload(
        {
            "name": spec.id,
            "description": spec.summary,
            "concept_mapping": asdict(spec.concept_mapping),
            **spec.overrides,
        }
    )


def run_candidate_matrix(
    lab_root: Path = DEFAULT_LAB_ROOT,
    harness_runner: Callable[..., Any] = run_harness,
    calibration_profile_path: Path | None = None,
    replay_bundle_path: Path | None = None,
    corpus_status_path: Path | None = None,
) -> PromotionManifest:
    layout = ensure_lab_layout(lab_root)
    candidates_dir = layout["candidates"]
    results_dir = layout["results"]
    baselines_dir = layout["baselines"]
    ref_root = lab_root.parent
    index_path = baselines_dir / BASELINE_FILES["index"]
    if not index_path.exists():
        raise FactoryError(f"baseline index missing: {index_path}")

    index = read_json(index_path)
    if not index.get("contract_checks", {}).get("passed", False):
        raise FactoryError("baseline contract checks failed; refresh baselines before running the matrix")

    calibration_profile_path = calibration_profile_path or (baselines_dir / BASELINE_FILES["calibration.profile"])
    if not calibration_profile_path.exists():
        raise FactoryError(
            f"calibration profile missing: {calibration_profile_path}. Run tools/build_calibration_profile.py first."
        )
    calibration_profile = load_calibration_profile(calibration_profile_path)

    calibration_report_path = baselines_dir / BASELINE_FILES["calibration.report"]
    if not calibration_report_path.exists():
        raise FactoryError(
            f"calibration report missing: {calibration_report_path}. Run tools/build_calibration_profile.py first."
        )
    calibration_report = load_calibration_report(calibration_report_path)

    replay_dir = layout["replay"]
    replay_bundle_path = replay_bundle_path or (replay_dir / REPLAY_FILES["bundle"])
    if not replay_bundle_path.exists():
        raise FactoryError(
            f"replay bundle missing: {replay_bundle_path}. Run tools/build_replay_bundle.py first."
        )
    replay_bundle = load_replay_bundle(replay_bundle_path)
    corpus_status_path = corpus_status_path or (replay_dir / REPLAY_FILES["status"])
    if not corpus_status_path.exists():
        raise FactoryError(
            f"replay corpus status missing: {corpus_status_path}. Run tools/build_replay_bundle.py first."
        )
    corpus_status = load_corpus_status(corpus_status_path)

    calibrated_control = apply_calibration_overrides(control_candidate(), calibration_profile.harness_overrides)
    control_metrics = calibration_report.calibrated_control_metrics
    evaluated_candidates: list[dict[str, Any]] = []
    promotable_candidates: list[str] = []

    for candidate_path in sorted(candidates_dir.glob("*.json")):
        spec = load_candidate_spec(candidate_path)
        candidate = candidate_spec_to_dynamics(spec)
        ontology_failures = validate_ontology_gate(candidate)

        if ontology_failures:
            result = CandidateResult(
                candidate_id=spec.id,
                ontology_gate_passed=False,
                mechanism_gate_passed=False,
                control_metrics=control_metrics,
                candidate_metrics={},
                metric_deltas={},
                ontology_gate_failures=ontology_failures,
                mechanism_gate_failures=["ontology gate failed; mechanism evaluation skipped"],
                promotable=False,
                calibration_profile_ref=path_ref(calibration_profile_path, root=ref_root),
                control_fit_error=calibration_report.fit_error,
                gated_under_calibration=True,
                replay_gate_passed=False,
                replay_ready=corpus_status.replay_ready,
                replay_bundle_ref=path_ref(replay_bundle_path, root=ref_root),
                replay_window_results=[],
                replay_blocking_reasons=list(corpus_status.blocking_reasons),
                gated_under_replay=True,
            )
        else:
            report = harness_runner(
                candidate=candidate,
                control=calibrated_control,
                seeds=DEFAULT_SEEDS,
                scenarios=DEFAULT_SCENARIOS,
            )
            control_drift = compute_metric_deltas(report.control.metrics, control_metrics)
            drifted_keys = [key for key, value in control_drift.items() if abs(value) > 0.0001]
            metric_failures, _ = compare_candidate_metrics(report.candidate.metrics, control_metrics)
            mechanism_failures = list(report.candidate.mechanism_gate_failures)
            for failure in metric_failures:
                if failure not in mechanism_failures:
                    mechanism_failures.append(failure)
            if drifted_keys:
                mechanism_failures.append(
                    "recorded calibrated control drifted from calibration report: " + ", ".join(drifted_keys)
                )

            mechanism_gate_passed = not mechanism_failures
            replay_window_results: list[dict[str, Any]] = []
            replay_gate_failures: list[str] = []
            replay_gate_passed = False
            if mechanism_gate_passed and corpus_status.replay_ready:
                replay_gate_passed = True
                for window in replay_bundle.windows:
                    replay_control = apply_calibration_overrides(control_candidate(), window.harness_overrides)
                    replay_report = harness_runner(
                        candidate=candidate,
                        control=replay_control,
                        seeds=DEFAULT_SEEDS,
                        scenarios=DEFAULT_SCENARIOS,
                    )
                    window_failures, _ = compare_candidate_metrics(
                        replay_report.candidate.metrics,
                        replay_report.control.metrics,
                    )
                    window_failures = list(replay_report.candidate.mechanism_gate_failures) + [
                        failure
                        for failure in window_failures
                        if failure not in replay_report.candidate.mechanism_gate_failures
                    ]
                    window_passed = not window_failures
                    replay_window_results.append(
                        {
                            "window": window.name,
                            "snapshot_ref": window.snapshot_ref,
                            "passed": window_passed,
                            "control_metrics": replay_report.control.metrics,
                            "candidate_metrics": replay_report.candidate.metrics,
                            "metric_deltas": compute_metric_deltas(
                                replay_report.candidate.metrics,
                                replay_report.control.metrics,
                            ),
                            "failures": window_failures,
                        }
                    )
                    if not window_passed:
                        replay_gate_passed = False
                        replay_gate_failures.extend([f"{window.name}: {failure}" for failure in window_failures])
            elif mechanism_gate_passed:
                replay_gate_failures.extend(corpus_status.blocking_reasons)
            mechanism_gate_failures = mechanism_failures + replay_gate_failures
            result = CandidateResult(
                candidate_id=spec.id,
                ontology_gate_passed=True,
                mechanism_gate_passed=mechanism_gate_passed,
                control_metrics=control_metrics,
                candidate_metrics=report.candidate.metrics,
                metric_deltas=compute_metric_deltas(report.candidate.metrics, control_metrics),
                ontology_gate_failures=[],
                mechanism_gate_failures=mechanism_gate_failures,
                promotable=(
                    mechanism_gate_passed
                    and replay_gate_passed
                    and report.candidate.metrics.get("new_nouns", 0.0) == 0.0
                ),
                calibration_profile_ref=path_ref(calibration_profile_path, root=ref_root),
                control_fit_error=calibration_report.fit_error,
                gated_under_calibration=True,
                replay_gate_passed=replay_gate_passed,
                replay_ready=corpus_status.replay_ready,
                replay_bundle_ref=path_ref(replay_bundle_path, root=ref_root),
                replay_window_results=replay_window_results,
                replay_blocking_reasons=list(corpus_status.blocking_reasons),
                gated_under_replay=True,
            )

        result_path = candidate_result_path(results_dir, spec.id)
        write_json(result_path, asdict(result))
        evaluated_candidates.append(
            {
                "candidate_id": spec.id,
                "result_ref": path_ref(result_path, root=ref_root),
                "promotable": result.promotable,
            }
        )
        if result.promotable:
            promotable_candidates.append(spec.id)

    manifest = PromotionManifest(
        generated_at=utc_now(),
        baseline_refs=index["baseline_refs"],
        evaluated_candidates=evaluated_candidates,
        promotable_candidates=promotable_candidates,
        calibration_profile_ref=path_ref(calibration_profile_path, root=ref_root),
        baseline_snapshot_ref=path_ref(index_path, root=ref_root),
        gated_under_calibration=True,
        replay_bundle_ref=path_ref(replay_bundle_path, root=ref_root),
        replay_ready=corpus_status.replay_ready,
        replay_blocking_reasons=list(corpus_status.blocking_reasons),
        latest_snapshot_ref=path_ref(index_path, root=ref_root),
        gated_under_replay=True,
    )
    write_json(results_dir / "promotion_manifest.json", asdict(manifest))
    return manifest
