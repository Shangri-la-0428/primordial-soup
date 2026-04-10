"""Replay protocol, corpus status, and bundle selection."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .artifacts import (
    CAPTURE_LABELS,
    CAPTURE_ORIGINS,
    DEFAULT_LAB_ROOT,
    MIN_REPLAY_DIVERSITY_SCORE,
    MIN_REPLAY_SNAPSHOTS,
    MIN_REPLAY_UNIQUE_WINDOWS,
    REPLAY_FILES,
    REPLAY_WINDOW_NAMES,
    CorpusStatus,
    FactoryError,
    ReplayBundle,
    ReplayReport,
    ReplayWindow,
    clamp01,
    ensure_lab_layout,
    path_ref,
    read_json,
    utc_now,
    write_json,
)
from .calibration import build_calibration_overrides, compute_calibration_axes


def normalize_capture_label(capture_label: str | None) -> str:
    normalized = (capture_label or "unlabeled").strip() or "unlabeled"
    if normalized not in CAPTURE_LABELS:
        raise FactoryError(
            "invalid capture_label "
            f"'{normalized}'; expected one of {', '.join(CAPTURE_LABELS)}"
        )
    return normalized


def normalize_capture_origin(capture_origin: str | None) -> str:
    normalized = (capture_origin or "manual-guided").strip() or "manual-guided"
    if normalized not in CAPTURE_ORIGINS:
        raise FactoryError(
            "invalid capture_origin "
            f"'{normalized}'; expected one of {', '.join(CAPTURE_ORIGINS)}"
        )
    return normalized


def evaluate_replay_protocol(
    axes: dict[str, float],
    *,
    selected_label: str | None = None,
) -> dict[str, Any]:
    recommended_labels: list[str] = []
    label_support: dict[str, bool] = {
        "quiet-baseline": False,
        "continuity-stress": False,
        "contamination-spike": False,
        "repair-window": False,
    }
    reasons: list[str] = []
    boundary_fragility = axes["boundary_fragility"]
    false_signal_stickiness = axes["false_signal_stickiness"]
    cross_space_leach = axes["cross_space_leach"]
    repair_capacity = axes["repair_capacity"]

    if boundary_fragility <= 0.25 and false_signal_stickiness <= 0.2 and cross_space_leach <= 0.2:
        label_support["quiet-baseline"] = True
        recommended_labels.append("quiet-baseline")
        reasons.append("quiet-baseline supported by low boundary fragility and low contamination axes")
    if boundary_fragility >= 0.55 and false_signal_stickiness < 0.65 and cross_space_leach < 0.65:
        label_support["continuity-stress"] = True
        recommended_labels.append("continuity-stress")
        reasons.append("continuity-stress supported by high boundary fragility without dominant contamination")
    if false_signal_stickiness >= 0.6 or cross_space_leach >= 0.6:
        label_support["contamination-spike"] = True
        recommended_labels.append("contamination-spike")
        reasons.append("contamination-spike supported by elevated false-signal stickiness or cross-space leach")
    if repair_capacity >= 0.45 and false_signal_stickiness < 0.6 and cross_space_leach < 0.6:
        label_support["repair-window"] = True
        recommended_labels.append("repair-window")
        reasons.append("repair-window supported by elevated repair capacity without active contamination spike")

    selected_label_supported = True
    blocking_reasons: list[str] = []
    if selected_label and selected_label != "unlabeled":
        selected_label_supported = label_support.get(selected_label, False)
        if not selected_label_supported:
            blocking_reasons.append(
                f"selected label '{selected_label}' is not supported by current replay protocol evaluation"
            )

    return {
        "recommended_labels": recommended_labels,
        "label_support": label_support,
        "selected_label": selected_label,
        "selected_label_supported": selected_label_supported,
        "reasons": reasons,
        "blocking_reasons": blocking_reasons,
    }


def _load_archive_indices(
    archive_root: Path,
    ref_root: Path,
) -> list[dict[str, Any]]:
    indices: list[dict[str, Any]] = []
    for index_path in sorted(archive_root.glob("*/index.json")):
        payload = read_json(index_path)
        if not payload.get("contract_checks", {}).get("passed", False):
            continue
        stack_signals = payload.get("stack_signals")
        if not stack_signals:
            continue
        payload["_snapshot_ref"] = path_ref(index_path, root=ref_root)
        payload["_snapshot_id"] = payload.get("snapshot_id", index_path.parent.name)
        payload["_capture_label"] = normalize_capture_label(payload.get("capture_label"))
        payload["_capture_origin"] = normalize_capture_origin(payload.get("capture_origin"))
        payload["_capture_note"] = payload.get("capture_note")
        payload["_protocol_eval"] = payload.get("protocol_eval", {})
        indices.append(payload)
    return indices


def _window_score(snapshot: dict[str, Any], window_name: str) -> float:
    axes = compute_calibration_axes(snapshot["stack_signals"])
    if window_name == "quiet-baseline":
        return axes["false_signal_stickiness"] + axes["cross_space_leach"]
    if window_name == "continuity-stress":
        return axes["boundary_fragility"]
    if window_name == "contamination-spike":
        return axes["false_signal_stickiness"] + axes["cross_space_leach"]
    if window_name == "repair-window":
        return axes["repair_capacity"]
    raise FactoryError(f"unknown replay window: {window_name}")


def _compute_replay_diversity(recent_snapshots: list[dict[str, Any]]) -> float:
    if not recent_snapshots:
        return 0.0
    axis_keys = (
        "boundary_fragility",
        "false_signal_stickiness",
        "cross_space_leach",
        "repair_capacity",
        "continuity_health",
    )
    axis_ranges: list[float] = []
    for key in axis_keys:
        values = [compute_calibration_axes(snapshot["stack_signals"])[key] for snapshot in recent_snapshots]
        axis_ranges.append(max(values) - min(values))
    return round(sum(axis_ranges) / len(axis_ranges), 4)


def _latest_snapshot_by_label(recent_snapshots: list[dict[str, Any]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for snapshot in recent_snapshots:
        label = snapshot["_capture_label"]
        latest[label] = snapshot["_snapshot_ref"]
    return latest


def _label_counts(recent_snapshots: list[dict[str, Any]]) -> dict[str, int]:
    counts = {label: 0 for label in CAPTURE_LABELS}
    for snapshot in recent_snapshots:
        counts[snapshot["_capture_label"]] += 1
    return counts


def _select_replay_window_snapshot(
    recent_snapshots: list[dict[str, Any]],
    window_name: str,
) -> tuple[dict[str, Any], str]:
    labeled = [snapshot for snapshot in recent_snapshots if snapshot["_capture_label"] == window_name]
    supported_labeled = [
        snapshot for snapshot in labeled if snapshot["_protocol_eval"].get("selected_label_supported", False)
    ]
    if supported_labeled:
        return supported_labeled[-1], "label-supported"
    if labeled:
        return labeled[-1], "label-unsupported"
    if window_name == "quiet-baseline":
        return min(recent_snapshots, key=lambda snapshot: _window_score(snapshot, "quiet-baseline")), "heuristic"
    if window_name == "continuity-stress":
        return max(recent_snapshots, key=lambda snapshot: _window_score(snapshot, "continuity-stress")), "heuristic"
    if window_name == "contamination-spike":
        return max(recent_snapshots, key=lambda snapshot: _window_score(snapshot, "contamination-spike")), "heuristic"
    if window_name == "repair-window":
        return max(recent_snapshots, key=lambda snapshot: _window_score(snapshot, "repair-window")), "heuristic"
    raise FactoryError(f"unknown replay window: {window_name}")


def build_replay_bundle(
    lab_root: Path = DEFAULT_LAB_ROOT,
) -> tuple[ReplayBundle, ReplayReport, CorpusStatus]:
    layout = ensure_lab_layout(lab_root)
    archive_root = layout["archive"]
    replay_dir = layout["replay"]
    ref_root = lab_root.parent

    archive_indices = _load_archive_indices(archive_root, ref_root)
    if not archive_indices:
        raise FactoryError("replay bundle requires at least 1 archived baseline snapshot")

    recent_snapshots = archive_indices[-5:]
    windows: list[ReplayWindow] = []
    window_summaries: list[dict[str, Any]] = []
    selection_reasoning: dict[str, str] = {}
    heuristic_fallback_windows: list[str] = []
    unsupported_labels: list[str] = []
    protocol_mismatches: list[str] = []
    for window_name in REPLAY_WINDOW_NAMES:
        snapshot, selection_mode = _select_replay_window_snapshot(recent_snapshots, window_name)
        axes = compute_calibration_axes(snapshot["stack_signals"])
        overrides = build_calibration_overrides(axes)
        windows.append(
            ReplayWindow(
                name=window_name,
                snapshot_id=snapshot["_snapshot_id"],
                snapshot_ref=snapshot["_snapshot_ref"],
                stack_signals=snapshot["stack_signals"],
                axes=axes,
                harness_overrides=overrides,
            )
        )
        window_summaries.append(
            {
                "name": window_name,
                "snapshot_id": snapshot["_snapshot_id"],
                "snapshot_ref": snapshot["_snapshot_ref"],
                "capture_label": snapshot["_capture_label"],
                "capture_origin": snapshot["_capture_origin"],
                "capture_note": snapshot["_capture_note"],
                "selection_mode": selection_mode,
                "protocol_eval": snapshot["_protocol_eval"],
                "axes": axes,
            }
        )
        if selection_mode == "label-supported":
            selection_reasoning[window_name] = "selected latest snapshot with matching capture_label"
        elif selection_mode == "label-unsupported":
            unsupported_labels.append(window_name)
            protocol_mismatches.extend(snapshot["_protocol_eval"].get("blocking_reasons", []))
            selection_reasoning[window_name] = (
                "selected latest labeled snapshot, but replay protocol does not support that label"
            )
        else:
            heuristic_fallback_windows.append(window_name)
            selection_reasoning[window_name] = "selected by heuristic fallback because matching capture_label is missing"

    window_map = {window.name: window.snapshot_id for window in windows}
    unique_snapshot_ids = sorted({window.snapshot_id for window in windows})
    diversity_score = _compute_replay_diversity(recent_snapshots)
    label_counts = _label_counts(recent_snapshots)
    latest_by_label = _latest_snapshot_by_label(recent_snapshots)
    required_labels = list(REPLAY_WINDOW_NAMES)
    missing_labels = [label for label in required_labels if label_counts.get(label, 0) == 0]
    blocking_reasons: list[str] = []
    if len(recent_snapshots) < MIN_REPLAY_SNAPSHOTS:
        blocking_reasons.append(
            f"replay corpus needs at least {MIN_REPLAY_SNAPSHOTS} recent snapshots ({len(recent_snapshots)} present)"
        )
    if missing_labels:
        blocking_reasons.append("missing labeled replay windows: " + ", ".join(missing_labels))
    if unsupported_labels:
        blocking_reasons.append("labeled replay windows not supported by protocol: " + ", ".join(unsupported_labels))
    for mismatch in protocol_mismatches:
        if mismatch not in blocking_reasons:
            blocking_reasons.append(mismatch)
    for window_name in heuristic_fallback_windows:
        blocking_reasons.append(
            f"{window_name} selected by heuristic fallback because no labeled snapshot exists"
        )
    if len(unique_snapshot_ids) < MIN_REPLAY_UNIQUE_WINDOWS:
        blocking_reasons.append("replay windows collapsed onto too few distinct snapshots")
    if diversity_score < MIN_REPLAY_DIVERSITY_SCORE:
        blocking_reasons.append(
            f"replay archive diversity below threshold ({diversity_score:.4f} < {MIN_REPLAY_DIVERSITY_SCORE:.2f})"
        )
    replay_ready = not blocking_reasons
    window_coverage = {
        "windows": window_map,
        "unique_snapshot_count": len(unique_snapshot_ids),
        "unique_snapshot_ids": unique_snapshot_ids,
        "recent_snapshot_count": len(recent_snapshots),
        "selection_modes": {summary["name"]: summary["selection_mode"] for summary in window_summaries},
    }

    captured_at = utc_now()
    bundle = ReplayBundle(
        bundle_id=f"replay-calibrated-v1-{captured_at.replace(':', '').replace('-', '')}",
        generated_at=captured_at,
        snapshot_refs=[snapshot["_snapshot_ref"] for snapshot in recent_snapshots],
        windows=windows,
        replay_ready=replay_ready,
        diversity_score=diversity_score,
        window_coverage=window_coverage,
        blocking_reasons=blocking_reasons,
    )
    bundle_path = replay_dir / REPLAY_FILES["bundle"]
    report_path = replay_dir / REPLAY_FILES["report"]
    status_path = replay_dir / REPLAY_FILES["status"]
    write_json(bundle_path, asdict(bundle))
    report = ReplayReport(
        generated_at=captured_at,
        bundle_ref=path_ref(bundle_path, root=ref_root),
        window_summaries=window_summaries,
        selection_reasoning=selection_reasoning,
        replay_ready=replay_ready,
        diversity_score=diversity_score,
        window_coverage=window_coverage,
        blocking_reasons=blocking_reasons,
    )
    write_json(report_path, asdict(report))
    next_recommended_label = missing_labels[0] if missing_labels else None
    status = CorpusStatus(
        captured_at=captured_at,
        archive_count=len(archive_indices),
        label_counts=label_counts,
        latest_by_label=latest_by_label,
        missing_labels=missing_labels,
        unsupported_labels=unsupported_labels,
        fallback_windows=heuristic_fallback_windows,
        protocol_mismatches=protocol_mismatches,
        replay_ready=replay_ready,
        blocking_reasons=blocking_reasons,
        diversity_score=diversity_score,
        next_recommended_label=next_recommended_label,
        heuristic_fallback_windows=heuristic_fallback_windows,
    )
    write_json(status_path, asdict(status))
    return bundle, report, status
