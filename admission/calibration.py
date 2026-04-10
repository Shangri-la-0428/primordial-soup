"""Calibration axes and control fitting."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from harness import DEFAULT_SCENARIOS, DEFAULT_SEEDS, candidate_from_payload, control_candidate, run_harness

from .artifacts import (
    BASELINE_FILES,
    CALIBRATABLE_KEYS,
    CONTINUITY_HEALTH_LOOKUP,
    DEFAULT_LAB_ROOT,
    CalibrationProfile,
    CalibrationReport,
    FactoryError,
    ensure_lab_layout,
    path_ref,
    read_json,
    utc_now,
    write_json,
    clamp01,
)


def _substrate_activity_score(activity: str | None) -> float:
    if not activity:
        return 0.5
    return CONTINUITY_HEALTH_LOOKUP.get(activity, 0.5)


def compute_calibration_axes(stack_signals: dict[str, Any]) -> dict[str, float]:
    psyche = stack_signals.get("psyche", {})
    thronglets = stack_signals.get("thronglets", {})
    boundary_fragility = clamp01(
        (
            min(abs(float(psyche.get("boundary_delta", 0.0))), 10.0) / 10.0
            + clamp01(float(psyche.get("prediction_error", 0.0)))
            + min(int(psyche.get("issue_count", 0)), 5) / 5.0
        )
        / 3.0
    )
    false_signal_stickiness = clamp01(float(thronglets.get("false_signal_pressure", 0.0)))
    cross_space_leach = clamp01(float(thronglets.get("cross_space_contamination_rate", 0.0)))
    active_spaces = max(int(thronglets.get("active_spaces_24h", 0)), 1)
    repair_capacity = clamp01(int(thronglets.get("recoverable_spaces_24h", 0)) / active_spaces)
    continuity_health = _substrate_activity_score(thronglets.get("substrate_activity"))
    return {
        "boundary_fragility": round(boundary_fragility, 4),
        "false_signal_stickiness": round(false_signal_stickiness, 4),
        "cross_space_leach": round(cross_space_leach, 4),
        "repair_capacity": round(repair_capacity, 4),
        "continuity_health": round(continuity_health, 4),
    }


def build_calibration_overrides(axes: dict[str, float]) -> dict[str, float]:
    boundary_fragility = axes["boundary_fragility"]
    false_signal_stickiness = axes["false_signal_stickiness"]
    cross_space_leach = axes["cross_space_leach"]
    repair_capacity = axes["repair_capacity"]
    continuity_health = axes["continuity_health"]

    overrides = {
        "collapse_order_floor": round(18.0 + boundary_fragility * 6.0, 4),
        "collapse_boundary_floor": round(18.0 + boundary_fragility * 6.0, 4),
        "collapse_recovery_nudge": round(boundary_fragility * 6.0, 4),
        "wrong_signal_decay": round(0.56 + false_signal_stickiness * 0.3, 4),
        "false_signal_penalty": round(0.32 + false_signal_stickiness * 0.5, 4),
        "cross_space_leakage": round(0.06 + cross_space_leach * 0.2, 4),
        "space_isolation_strength": round(max(0.45, 0.94 - cross_space_leach * 0.4), 4),
        "local_repair_bias": round(repair_capacity * 0.2, 4),
        "trace_recovery_bonus": round(repair_capacity * 0.24, 4),
        "peer_memory_resilience": round(0.44 + continuity_health * 0.2, 4),
        "mixed_residue_bias": round(0.1 + continuity_health * 0.2, 4),
    }
    invalid = [key for key in overrides if key not in CALIBRATABLE_KEYS]
    if invalid:
        raise FactoryError("calibration profile generated invalid harness overrides: " + ", ".join(invalid))
    return overrides


def apply_calibration_overrides(base_candidate, overrides: dict[str, Any]):
    if not overrides:
        return base_candidate
    invalid = [key for key in overrides if key not in CALIBRATABLE_KEYS]
    if invalid:
        raise FactoryError("calibration overrides contain unsupported keys: " + ", ".join(invalid))
    return candidate_from_payload(overrides, base_candidate=base_candidate)


def compute_fit_targets(stack_signals: dict[str, Any]) -> dict[str, float]:
    thronglets = stack_signals.get("thronglets", {})
    active_spaces = max(int(thronglets.get("active_spaces_24h", 0)), 1)
    return {
        "false_signal_pressure_proxy": round(
            clamp01(float(thronglets.get("false_signal_pressure", 0.0))),
            4,
        ),
        "cross_space_contamination_proxy": round(
            clamp01(float(thronglets.get("cross_space_contamination_rate", 0.0))),
            4,
        ),
        "recovery_capacity_proxy": round(
            clamp01(int(thronglets.get("recoverable_spaces_24h", 0)) / active_spaces),
            4,
        ),
        "continuity_health_proxy": round(
            _substrate_activity_score(thronglets.get("substrate_activity")),
            4,
        ),
    }


def compute_fit_proxies(control_metrics: dict[str, Any]) -> dict[str, float]:
    false_signal_pressure = clamp01(1.0 - float(control_metrics.get("false_signal_suppression", 0.0)))
    cross_space_contamination = clamp01(float(control_metrics.get("cross_space_contamination", 0.0)))
    repair_balance = clamp01(float(control_metrics.get("repair_signal_balance", 0.0)) / 3.0)
    recovery_capacity = clamp01(
        (
            float(control_metrics.get("local_repair_precision", 0.0))
            + repair_balance
        )
        / 2.0
    )
    continuity_health = clamp01(float(control_metrics.get("continuity_survival", 0.0)))
    return {
        "false_signal_pressure_proxy": round(false_signal_pressure, 4),
        "cross_space_contamination_proxy": round(cross_space_contamination, 4),
        "recovery_capacity_proxy": round(recovery_capacity, 4),
        "continuity_health_proxy": round(continuity_health, 4),
    }


def compute_fit_error(fit_targets: dict[str, float], fit_proxies: dict[str, float]) -> float:
    deltas = [abs(fit_targets[key] - fit_proxies[key]) for key in (
        "false_signal_pressure_proxy",
        "cross_space_contamination_proxy",
        "recovery_capacity_proxy",
        "continuity_health_proxy",
    )]
    return round(sum(deltas) / len(deltas), 4)


def build_calibration_profile(
    lab_root: Path = DEFAULT_LAB_ROOT,
    harness_runner: Callable[..., Any] = run_harness,
) -> tuple[CalibrationProfile, CalibrationReport]:
    baselines_dir = ensure_lab_layout(lab_root)["baselines"]
    ref_root = lab_root.parent
    index_path = baselines_dir / BASELINE_FILES["index"]
    if not index_path.exists():
        raise FactoryError(f"baseline index missing: {index_path}")

    index = read_json(index_path)
    if not index.get("contract_checks", {}).get("passed", False):
        raise FactoryError("baseline contract checks failed; refresh baselines before calibration")

    stack_signals = index.get("stack_signals", {})
    axes = compute_calibration_axes(stack_signals)
    proposed_overrides = build_calibration_overrides(axes)
    fit_targets = compute_fit_targets(stack_signals)

    raw_control = control_candidate()
    raw_report = harness_runner(candidate=raw_control, control=raw_control, seeds=DEFAULT_SEEDS, scenarios=DEFAULT_SCENARIOS)
    raw_metrics = raw_report.control.metrics
    raw_proxies = compute_fit_proxies(raw_metrics)
    raw_fit_error = compute_fit_error(fit_targets, raw_proxies)

    calibrated_control = apply_calibration_overrides(control_candidate(), proposed_overrides)
    calibrated_report = harness_runner(
        candidate=calibrated_control,
        control=calibrated_control,
        seeds=DEFAULT_SEEDS,
        scenarios=DEFAULT_SCENARIOS,
    )
    calibrated_metrics = calibrated_report.control.metrics
    calibrated_proxies = compute_fit_proxies(calibrated_metrics)
    calibrated_fit_error = compute_fit_error(fit_targets, calibrated_proxies)

    if calibrated_fit_error <= raw_fit_error:
        effective_overrides = proposed_overrides
        effective_metrics = calibrated_metrics
        effective_proxies = calibrated_proxies
        effective_fit_error = calibrated_fit_error
    else:
        effective_overrides = {}
        effective_metrics = raw_metrics
        effective_proxies = raw_proxies
        effective_fit_error = raw_fit_error

    captured_at = utc_now()
    profile = CalibrationProfile(
        profile_id=f"read-only-calibration-v1-{captured_at.replace(':', '').replace('-', '')}",
        captured_at=captured_at,
        baseline_refs=index["baseline_refs"],
        axes=axes,
        harness_overrides=effective_overrides,
    )

    profile_path = baselines_dir / BASELINE_FILES["calibration.profile"]
    report_path = baselines_dir / BASELINE_FILES["calibration.report"]

    write_json(profile_path, asdict(profile))
    report = CalibrationReport(
        captured_at=captured_at,
        baseline_refs=index["baseline_refs"],
        profile_ref=path_ref(profile_path, root=ref_root),
        baseline_live_signals=stack_signals,
        profile_axes=axes,
        applied_harness_overrides=effective_overrides,
        fit_targets=fit_targets,
        calibrated_control_metrics=effective_metrics,
        fit_proxies=effective_proxies,
        fit_error=effective_fit_error,
        baseline_fit_error=raw_fit_error,
    )
    write_json(report_path, asdict(report))

    index["calibration_refs"] = {
        "calibration.profile": path_ref(profile_path, root=ref_root),
        "calibration.report": path_ref(report_path, root=ref_root),
    }
    write_json(index_path, index)
    return profile, report
