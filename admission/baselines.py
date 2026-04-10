"""Baseline collection and archive writing."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from harness import (
    FROZEN_IDENTITY_PRIMITIVES,
    FROZEN_SHARED_CARRIERS,
    FROZEN_SIGNAL_KINDS,
    FROZEN_TRACE_TAXONOMY,
)

from .artifacts import (
    BASELINE_FILES,
    BASELINE_SCHEMA_VERSION,
    DEFAULT_LAB_ROOT,
    DEFAULT_PSYCHE_ROOT,
    DEFAULT_THRONGLETS_ROOT,
    REPO_ROOT,
    BaselineSnapshot,
    FactoryError,
    archive_index_refs,
    ensure_lab_layout,
    next_archive_snapshot_dir,
    path_ref,
    read_json,
    utc_now,
    write_json,
)
from .calibration import compute_calibration_axes
from .replay import evaluate_replay_protocol, normalize_capture_label, normalize_capture_origin


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise FactoryError("expected JSON output, got empty stdout")
    try:
        import json

        return json.loads(stripped)
    except json.JSONDecodeError:
        lines = text.splitlines()
        decoder = json.JSONDecoder()
        for index, line in enumerate(lines):
            if not line.lstrip().startswith("{"):
                continue
            candidate = "\n".join(lines[index:])
            try:
                payload, _ = decoder.raw_decode(candidate)
                return payload
            except json.JSONDecodeError:
                continue
    raise FactoryError("unable to extract JSON payload from command output")


def _run_command(args: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise FactoryError(
            f"command failed in {cwd}: {' '.join(args)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return _extract_json_payload(completed.stdout)


def build_harness_baseline_snapshot(
    payload: dict[str, Any],
    command: str,
    captured_at: str,
) -> BaselineSnapshot:
    return BaselineSnapshot(
        source="harness.control",
        schema_version=BASELINE_SCHEMA_VERSION,
        captured_at=captured_at,
        command=command,
        boundary_contract=payload["boundary_contract"],
        metrics=payload["control"]["metrics"],
    )


def build_psyche_baseline_snapshot(
    payload: dict[str, Any],
    command: str,
    captured_at: str,
) -> BaselineSnapshot:
    fixture = payload.get("fixture", {})
    external_continuity = fixture.get("externalContinuity", {})
    return BaselineSnapshot(
        source="psyche.probe",
        schema_version=BASELINE_SCHEMA_VERSION,
        captured_at=captured_at,
        command=command,
        boundary_contract={
            "identity_primitives": fixture.get("frozenIdentityPrimitives", []),
            "signal_kinds": fixture.get("frozenSignalKinds", []),
            "trace_taxonomy": fixture.get("frozenTraceTaxonomy", []),
            "external_continuity_version": external_continuity.get("version"),
            "external_continuity_provider": external_continuity.get("provider"),
            "external_continuity_mode": external_continuity.get("mode"),
        },
        metrics={
            "ok": payload.get("ok"),
            "canonical_host_surface": payload.get("canonicalHostSurface"),
            "external_continuity_available": payload.get("externalContinuityAvailable"),
            "overlay": payload.get("overlay"),
            "trajectory": payload.get("trajectory"),
            "degradation": payload.get("degradation"),
            "boundary_stress": payload.get("boundaryStress"),
        },
    )


def build_thronglets_baseline_snapshot(
    payload: dict[str, Any],
    command: str,
    captured_at: str,
) -> BaselineSnapshot:
    return BaselineSnapshot(
        source="thronglets.eval-emergence",
        schema_version=BASELINE_SCHEMA_VERSION,
        captured_at=captured_at,
        command=command,
        boundary_contract={},
        metrics={
            "project_scope": payload.get("project_scope"),
            "signal_eval": payload.get("signal_eval"),
            "workspace_emergence": payload.get("workspace_emergence"),
            "substrate_activity": payload.get("substrate_activity"),
        },
    )


def extract_stack_signals(
    psyche_snapshot: BaselineSnapshot,
    thronglets_snapshot: BaselineSnapshot,
) -> dict[str, Any]:
    psyche_metrics = psyche_snapshot.metrics
    boundary_stress = psyche_metrics.get("boundary_stress", {}) or {}
    degradation = psyche_metrics.get("degradation", {}) or {}
    trajectory = psyche_metrics.get("trajectory", {}) or {}

    thronglets_metrics = thronglets_snapshot.metrics
    workspace_emergence = thronglets_metrics.get("workspace_emergence", {}) or {}
    substrate_activity = thronglets_metrics.get("substrate_activity", {}) or {}

    return {
        "psyche": {
            "boundary_delta": float(boundary_stress.get("boundaryDelta", 0.0) or 0.0),
            "prediction_error": float(degradation.get("predictionError", 0.0) or 0.0),
            "trajectory_kind": trajectory.get("kind"),
            "issue_count": int(degradation.get("issueCount", 0) or 0),
        },
        "thronglets": {
            "false_signal_pressure": float(workspace_emergence.get("false_signal_pressure", 0.0) or 0.0),
            "cross_space_contamination_rate": float(
                workspace_emergence.get("cross_space_contamination_rate", 0.0) or 0.0
            ),
            "recoverable_spaces_24h": int(workspace_emergence.get("recoverable_spaces_24h", 0) or 0),
            "active_spaces_24h": int(workspace_emergence.get("active_spaces_24h", 0) or 0),
            "substrate_activity": substrate_activity.get("activity"),
        },
    }


def summarize_stack_state(
    harness_snapshot: BaselineSnapshot,
    psyche_snapshot: BaselineSnapshot,
    thronglets_snapshot: BaselineSnapshot,
    *,
    capture_label: str | None = None,
) -> dict[str, Any]:
    normalized_capture_label = normalize_capture_label(capture_label)
    contract_failures = validate_stack_contracts(harness_snapshot, psyche_snapshot)
    stack_signals = extract_stack_signals(psyche_snapshot, thronglets_snapshot)
    protocol_eval = evaluate_replay_protocol(
        compute_calibration_axes(stack_signals),
        selected_label=normalized_capture_label,
    )
    return {
        "boundary_contract": harness_snapshot.boundary_contract,
        "stack_signals": stack_signals,
        "protocol_eval": protocol_eval,
        "contract_checks": {
            "passed": not contract_failures,
            "failures": contract_failures,
        },
    }


def validate_stack_contracts(
    harness_snapshot: BaselineSnapshot,
    psyche_snapshot: BaselineSnapshot,
) -> list[str]:
    failures: list[str] = []
    harness_contract = harness_snapshot.boundary_contract
    psyche_contract = psyche_snapshot.boundary_contract

    if harness_contract.get("identity_primitives") != list(FROZEN_IDENTITY_PRIMITIVES):
        failures.append("harness identity primitives drifted from frozen ontology")
    if harness_contract.get("shared_carriers") != list(FROZEN_SHARED_CARRIERS):
        failures.append("harness shared carriers drifted from frozen ontology")
    if harness_contract.get("signal_kinds") != list(FROZEN_SIGNAL_KINDS):
        failures.append("harness signal kinds drifted from frozen ontology")
    if harness_contract.get("trace_taxonomy") != list(FROZEN_TRACE_TAXONOMY):
        failures.append("harness trace taxonomy drifted from frozen ontology")
    if harness_contract.get("external_continuity_version") != 1:
        failures.append("harness external continuity version drifted from 1")

    if psyche_contract.get("identity_primitives") != list(FROZEN_IDENTITY_PRIMITIVES):
        failures.append("psyche probe identity primitives drifted from frozen ontology")
    if psyche_contract.get("signal_kinds") != list(FROZEN_SIGNAL_KINDS):
        failures.append("psyche probe signal kinds drifted from frozen ontology")
    if psyche_contract.get("trace_taxonomy") != list(FROZEN_TRACE_TAXONOMY):
        failures.append("psyche probe trace taxonomy drifted from frozen ontology")
    if psyche_contract.get("external_continuity_version") != 1:
        failures.append("psyche probe external continuity version drifted from 1")
    if psyche_contract.get("external_continuity_provider") != "thronglets":
        failures.append("psyche probe external continuity provider drifted from thronglets")
    if psyche_contract.get("external_continuity_mode") != "optional":
        failures.append("psyche probe external continuity mode drifted from optional")

    return failures


def _collect_stack_snapshots(
    *,
    repo_root: Path,
    psyche_root: Path,
    thronglets_root: Path,
    command_runner: Callable[[list[str], Path], dict[str, Any]],
    captured_at: str,
    thronglets_data_dir: Path | None = None,
) -> tuple[BaselineSnapshot, BaselineSnapshot, BaselineSnapshot]:
    harness_command = "python3 run.py --harness --harness-json"
    psyche_command = "npm run probe"
    thronglets_args = ["cargo", "run", "--"]
    if thronglets_data_dir is not None:
        thronglets_args.extend(["--data-dir", str(thronglets_data_dir)])
    thronglets_args.extend(
        [
            "eval-emergence",
            "--global",
            "--hours",
            "168",
            "--max-sessions",
            "10",
            "--json",
        ]
    )
    thronglets_command = " ".join(thronglets_args)

    harness_payload = command_runner(
        [sys.executable, str(repo_root / "run.py"), "--harness", "--harness-json"],
        repo_root,
    )
    psyche_payload = command_runner(["npm", "run", "probe"], psyche_root)
    thronglets_payload = command_runner(thronglets_args, thronglets_root)

    harness_snapshot = build_harness_baseline_snapshot(harness_payload, harness_command, captured_at)
    psyche_snapshot = build_psyche_baseline_snapshot(psyche_payload, psyche_command, captured_at)
    thronglets_snapshot = build_thronglets_baseline_snapshot(
        thronglets_payload,
        thronglets_command,
        captured_at,
    )
    return harness_snapshot, psyche_snapshot, thronglets_snapshot


def probe_stack_state(
    *,
    repo_root: Path = REPO_ROOT,
    psyche_root: Path = DEFAULT_PSYCHE_ROOT,
    thronglets_root: Path = DEFAULT_THRONGLETS_ROOT,
    command_runner: Callable[[list[str], Path], dict[str, Any]] = _run_command,
    capture_label: str | None = None,
    thronglets_data_dir: Path | None = None,
) -> dict[str, Any]:
    captured_at = utc_now()
    harness_snapshot, psyche_snapshot, thronglets_snapshot = _collect_stack_snapshots(
        repo_root=repo_root,
        psyche_root=psyche_root,
        thronglets_root=thronglets_root,
        command_runner=command_runner,
        captured_at=captured_at,
        thronglets_data_dir=thronglets_data_dir,
    )
    summary = summarize_stack_state(
        harness_snapshot,
        psyche_snapshot,
        thronglets_snapshot,
        capture_label=capture_label,
    )
    return {
        "captured_at": captured_at,
        "capture_label": normalize_capture_label(capture_label),
        **summary,
    }


def write_baseline_artifacts(
    lab_root: Path,
    harness_snapshot: BaselineSnapshot,
    psyche_snapshot: BaselineSnapshot,
    thronglets_snapshot: BaselineSnapshot,
    capture_label: str | None = None,
    capture_note: str | None = None,
    capture_origin: str | None = None,
) -> dict[str, Any]:
    layout = ensure_lab_layout(lab_root)
    baselines_dir = layout["baselines"]
    archive_dir = layout["archive"]
    ref_root = lab_root.parent

    harness_path = baselines_dir / BASELINE_FILES["harness.control"]
    psyche_path = baselines_dir / BASELINE_FILES["psyche.probe"]
    thronglets_path = baselines_dir / BASELINE_FILES["thronglets.eval-emergence"]
    index_path = baselines_dir / BASELINE_FILES["index"]
    normalized_capture_label = normalize_capture_label(capture_label)
    normalized_capture_origin = normalize_capture_origin(capture_origin)
    normalized_capture_note = (capture_note or "").strip() or None
    if normalized_capture_label != "unlabeled" and not normalized_capture_note:
        raise FactoryError("capture_note is required for labeled replay captures")

    existing_index: dict[str, Any] = {}
    if index_path.exists():
        existing_index = read_json(index_path)

    write_json(harness_path, asdict(harness_snapshot))
    write_json(psyche_path, asdict(psyche_snapshot))
    write_json(thronglets_path, asdict(thronglets_snapshot))

    snapshot_id, snapshot_dir = next_archive_snapshot_dir(archive_dir, harness_snapshot.captured_at)
    archived_harness_path = snapshot_dir / BASELINE_FILES["harness.control"]
    archived_psyche_path = snapshot_dir / BASELINE_FILES["psyche.probe"]
    archived_thronglets_path = snapshot_dir / BASELINE_FILES["thronglets.eval-emergence"]
    archived_index_path = snapshot_dir / BASELINE_FILES["index"]

    write_json(archived_harness_path, asdict(harness_snapshot))
    write_json(archived_psyche_path, asdict(psyche_snapshot))
    write_json(archived_thronglets_path, asdict(thronglets_snapshot))

    summary = summarize_stack_state(
        harness_snapshot,
        psyche_snapshot,
        thronglets_snapshot,
        capture_label=normalized_capture_label,
    )
    stack_signals = summary["stack_signals"]
    protocol_eval = summary["protocol_eval"]
    archived_index = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "captured_at": harness_snapshot.captured_at,
        "snapshot_id": snapshot_id,
        "capture_label": normalized_capture_label,
        "capture_note": normalized_capture_note,
        "capture_origin": normalized_capture_origin,
        "baseline_refs": {
            "harness.control": path_ref(archived_harness_path, root=ref_root),
            "psyche.probe": path_ref(archived_psyche_path, root=ref_root),
            "thronglets.eval-emergence": path_ref(archived_thronglets_path, root=ref_root),
        },
        "boundary_contract": harness_snapshot.boundary_contract,
        "stack_signals": stack_signals,
        "protocol_eval": protocol_eval,
        "contract_checks": summary["contract_checks"],
    }
    write_json(archived_index_path, archived_index)

    archive_refs = archive_index_refs(archive_dir, ref_root)
    index = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "captured_at": harness_snapshot.captured_at,
        "latest_snapshot_id": snapshot_id,
        "capture_label": normalized_capture_label,
        "capture_note": normalized_capture_note,
        "capture_origin": normalized_capture_origin,
        "baseline_refs": {
            "harness.control": path_ref(harness_path, root=ref_root),
            "psyche.probe": path_ref(psyche_path, root=ref_root),
            "thronglets.eval-emergence": path_ref(thronglets_path, root=ref_root),
        },
        "archive_refs": archive_refs,
        "boundary_contract": harness_snapshot.boundary_contract,
        "stack_signals": stack_signals,
        "protocol_eval": protocol_eval,
        "contract_checks": summary["contract_checks"],
        "calibration_refs": existing_index.get("calibration_refs", {}),
    }
    write_json(index_path, index)
    return index


def collect_stack_baselines(
    lab_root: Path = DEFAULT_LAB_ROOT,
    repo_root: Path = REPO_ROOT,
    psyche_root: Path = DEFAULT_PSYCHE_ROOT,
    thronglets_root: Path = DEFAULT_THRONGLETS_ROOT,
    command_runner: Callable[[list[str], Path], dict[str, Any]] = _run_command,
    capture_label: str | None = None,
    capture_note: str | None = None,
    capture_origin: str | None = None,
    thronglets_data_dir: Path | None = None,
) -> dict[str, Any]:
    captured_at = utc_now()
    harness_snapshot, psyche_snapshot, thronglets_snapshot = _collect_stack_snapshots(
        repo_root=repo_root,
        psyche_root=psyche_root,
        thronglets_root=thronglets_root,
        command_runner=command_runner,
        captured_at=captured_at,
        thronglets_data_dir=thronglets_data_dir,
    )
    return write_baseline_artifacts(
        lab_root,
        harness_snapshot,
        psyche_snapshot,
        thronglets_snapshot,
        capture_label=capture_label,
        capture_note=capture_note,
        capture_origin=capture_origin,
    )
