"""Shared artifact schemas, constants, and filesystem helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness import ConceptMapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = REPO_ROOT.parent
DEFAULT_LAB_ROOT = REPO_ROOT / "lab"
DEFAULT_PSYCHE_ROOT = DESKTOP_ROOT / "oasyce_psyche"
DEFAULT_THRONGLETS_ROOT = DESKTOP_ROOT / "Thronglets"

BASELINE_SCHEMA_VERSION = 1
CANDIDATE_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
PROMOTION_SCHEMA_VERSION = 1
CALIBRATION_SCHEMA_VERSION = 1
REPLAY_SCHEMA_VERSION = 1

BASELINE_FILES = {
    "harness.control": "harness.control.json",
    "psyche.probe": "psyche.probe.json",
    "thronglets.eval-emergence": "thronglets.eval-emergence.json",
    "index": "index.json",
    "calibration.profile": "calibration.profile.json",
    "calibration.report": "calibration.report.json",
}

REPLAY_FILES = {
    "bundle": "replay.bundle.json",
    "report": "replay.report.json",
    "status": "corpus.status.json",
}

CAPTURE_LABELS = (
    "quiet-baseline",
    "continuity-stress",
    "contamination-spike",
    "repair-window",
    "unlabeled",
)

CAPTURE_ORIGINS = (
    "stack-readonly",
    "manual-guided",
)

REPLAY_WINDOW_NAMES = (
    "quiet-baseline",
    "continuity-stress",
    "contamination-spike",
    "repair-window",
)

MIN_REPLAY_SNAPSHOTS = 5
MIN_REPLAY_UNIQUE_WINDOWS = 3
MIN_REPLAY_DIVERSITY_SCORE = 0.15

CALIBRATABLE_KEYS = {
    "collapse_order_floor",
    "collapse_boundary_floor",
    "collapse_recovery_nudge",
    "wrong_signal_decay",
    "false_signal_penalty",
    "cross_space_leakage",
    "space_isolation_strength",
    "local_repair_bias",
    "trace_recovery_bonus",
    "peer_memory_resilience",
    "mixed_residue_bias",
}

FIT_TARGET_KEYS = (
    "false_signal_pressure_proxy",
    "cross_space_contamination_proxy",
    "recovery_capacity_proxy",
    "continuity_health_proxy",
)

CONTINUITY_HEALTH_LOOKUP = {
    "quiet": 0.2,
    "learning": 0.6,
    "active": 0.8,
    "converging": 0.8,
}


class FactoryError(RuntimeError):
    """Raised when factory inputs or command outputs are invalid."""


@dataclass(slots=True)
class BaselineSnapshot:
    source: str
    schema_version: int
    captured_at: str
    command: str
    boundary_contract: dict[str, Any]
    metrics: dict[str, Any]


@dataclass(slots=True)
class CandidateSpec:
    id: str
    summary: str
    concept_mapping: ConceptMapping
    overrides: dict[str, Any]
    schema_version: int = CANDIDATE_SCHEMA_VERSION


@dataclass(slots=True)
class CalibrationProfile:
    profile_id: str
    captured_at: str
    baseline_refs: dict[str, str]
    axes: dict[str, float]
    harness_overrides: dict[str, float]
    schema_version: int = CALIBRATION_SCHEMA_VERSION


@dataclass(slots=True)
class CalibrationReport:
    captured_at: str
    baseline_refs: dict[str, str]
    profile_ref: str
    baseline_live_signals: dict[str, Any]
    profile_axes: dict[str, float]
    applied_harness_overrides: dict[str, float]
    fit_targets: dict[str, float]
    calibrated_control_metrics: dict[str, Any]
    fit_proxies: dict[str, float]
    fit_error: float
    baseline_fit_error: float
    schema_version: int = CALIBRATION_SCHEMA_VERSION


@dataclass(slots=True)
class ReplayWindow:
    name: str
    snapshot_id: str
    snapshot_ref: str
    stack_signals: dict[str, Any]
    axes: dict[str, float]
    harness_overrides: dict[str, float]


@dataclass(slots=True)
class ReplayBundle:
    bundle_id: str
    generated_at: str
    snapshot_refs: list[str]
    windows: list[ReplayWindow]
    replay_ready: bool
    diversity_score: float
    window_coverage: dict[str, Any]
    blocking_reasons: list[str]
    schema_version: int = REPLAY_SCHEMA_VERSION


@dataclass(slots=True)
class ReplayReport:
    generated_at: str
    bundle_ref: str
    window_summaries: list[dict[str, Any]]
    selection_reasoning: dict[str, str]
    replay_ready: bool
    diversity_score: float
    window_coverage: dict[str, Any]
    blocking_reasons: list[str]
    schema_version: int = REPLAY_SCHEMA_VERSION


@dataclass(slots=True)
class CorpusStatus:
    captured_at: str
    archive_count: int
    label_counts: dict[str, int]
    latest_by_label: dict[str, str]
    missing_labels: list[str]
    unsupported_labels: list[str]
    fallback_windows: list[str]
    protocol_mismatches: list[str]
    replay_ready: bool
    blocking_reasons: list[str]
    diversity_score: float
    next_recommended_label: str | None = None
    heuristic_fallback_windows: list[str] | None = None
    schema_version: int = REPLAY_SCHEMA_VERSION


@dataclass(slots=True)
class CandidateResult:
    candidate_id: str
    ontology_gate_passed: bool
    mechanism_gate_passed: bool
    control_metrics: dict[str, Any]
    candidate_metrics: dict[str, Any]
    metric_deltas: dict[str, float]
    ontology_gate_failures: list[str]
    mechanism_gate_failures: list[str]
    promotable: bool
    calibration_profile_ref: str | None = None
    control_fit_error: float | None = None
    gated_under_calibration: bool = False
    replay_gate_passed: bool = False
    replay_ready: bool = False
    replay_bundle_ref: str | None = None
    replay_window_results: list[dict[str, Any]] | None = None
    replay_blocking_reasons: list[str] | None = None
    gated_under_replay: bool = False
    schema_version: int = RESULT_SCHEMA_VERSION


@dataclass(slots=True)
class PromotionManifest:
    generated_at: str
    baseline_refs: dict[str, str]
    evaluated_candidates: list[dict[str, Any]]
    promotable_candidates: list[str]
    calibration_profile_ref: str | None = None
    baseline_snapshot_ref: str | None = None
    gated_under_calibration: bool = False
    replay_bundle_ref: str | None = None
    replay_ready: bool = False
    replay_blocking_reasons: list[str] | None = None
    latest_snapshot_ref: str | None = None
    gated_under_replay: bool = False
    schema_version: int = PROMOTION_SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def path_ref(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def resolve_ref(path_ref_value: str, root: Path = REPO_ROOT) -> Path:
    path = Path(path_ref_value)
    return path if path.is_absolute() else root / path


def ensure_lab_layout(lab_root: Path = DEFAULT_LAB_ROOT) -> dict[str, Path]:
    baselines = lab_root / "baselines"
    archive = baselines / "archive"
    candidates = lab_root / "candidates"
    results = lab_root / "results"
    replay = lab_root / "replay"
    for path in (baselines, archive, candidates, results, replay):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "lab": lab_root,
        "baselines": baselines,
        "archive": archive,
        "candidates": candidates,
        "results": results,
        "replay": replay,
    }


def snapshot_id_from_captured_at(captured_at: str) -> str:
    return captured_at.replace("-", "").replace(":", "").replace("+", "plus")


def next_archive_snapshot_dir(archive_root: Path, captured_at: str) -> tuple[str, Path]:
    base_id = snapshot_id_from_captured_at(captured_at)
    snapshot_id = base_id
    counter = 1
    snapshot_dir = archive_root / snapshot_id
    while snapshot_dir.exists():
        counter += 1
        snapshot_id = f"{base_id}-{counter}"
        snapshot_dir = archive_root / snapshot_id
    return snapshot_id, snapshot_dir


def archive_index_refs(archive_root: Path, ref_root: Path) -> dict[str, str]:
    archive_refs: dict[str, str] = {}
    for index_path in sorted(archive_root.glob("*/index.json")):
        archive_refs[index_path.parent.name] = path_ref(index_path, root=ref_root)
    return archive_refs


def candidate_result_path(results_dir: Path, candidate_id: str) -> Path:
    return results_dir / f"{candidate_id}.json"


def load_calibration_profile(path: Path) -> CalibrationProfile:
    payload = read_json(path)
    required = ("profile_id", "captured_at", "baseline_refs", "axes", "harness_overrides")
    missing = [key for key in required if key not in payload]
    if missing:
        raise FactoryError(f"calibration profile {path} missing required keys: {', '.join(missing)}")

    axes = payload["axes"]
    if sorted(axes.keys()) != sorted(
        [
            "boundary_fragility",
            "false_signal_stickiness",
            "cross_space_leach",
            "repair_capacity",
            "continuity_health",
        ]
    ):
        raise FactoryError(f"calibration profile {path} must define exactly the 5 frozen axes")

    overrides = payload["harness_overrides"]
    invalid = [key for key in overrides if key not in CALIBRATABLE_KEYS]
    if invalid:
        raise FactoryError(f"calibration profile {path} includes unsupported harness overrides: {', '.join(invalid)}")

    return CalibrationProfile(
        profile_id=payload["profile_id"],
        captured_at=payload["captured_at"],
        baseline_refs=payload["baseline_refs"],
        axes={key: float(value) for key, value in axes.items()},
        harness_overrides={key: float(value) for key, value in overrides.items()},
        schema_version=int(payload.get("schema_version", CALIBRATION_SCHEMA_VERSION)),
    )


def load_calibration_report(path: Path) -> CalibrationReport:
    payload = read_json(path)
    return CalibrationReport(
        captured_at=payload["captured_at"],
        baseline_refs=payload["baseline_refs"],
        profile_ref=payload["profile_ref"],
        baseline_live_signals=payload["baseline_live_signals"],
        profile_axes={key: float(value) for key, value in payload["profile_axes"].items()},
        applied_harness_overrides={
            key: float(value) for key, value in payload["applied_harness_overrides"].items()
        },
        fit_targets={key: float(value) for key, value in payload["fit_targets"].items()},
        calibrated_control_metrics=payload["calibrated_control_metrics"],
        fit_proxies={key: float(value) for key, value in payload["fit_proxies"].items()},
        fit_error=float(payload["fit_error"]),
        baseline_fit_error=float(payload.get("baseline_fit_error", payload["fit_error"])),
        schema_version=int(payload.get("schema_version", CALIBRATION_SCHEMA_VERSION)),
    )


def load_replay_bundle(path: Path) -> ReplayBundle:
    payload = read_json(path)
    required = (
        "bundle_id",
        "generated_at",
        "snapshot_refs",
        "windows",
        "replay_ready",
        "diversity_score",
        "window_coverage",
        "blocking_reasons",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise FactoryError(f"replay bundle {path} missing required keys: {', '.join(missing)}")
    windows = [
        ReplayWindow(
            name=window["name"],
            snapshot_id=window["snapshot_id"],
            snapshot_ref=window["snapshot_ref"],
            stack_signals=window["stack_signals"],
            axes={key: float(value) for key, value in window["axes"].items()},
            harness_overrides={key: float(value) for key, value in window["harness_overrides"].items()},
        )
        for window in payload["windows"]
    ]
    return ReplayBundle(
        bundle_id=payload["bundle_id"],
        generated_at=payload["generated_at"],
        snapshot_refs=list(payload["snapshot_refs"]),
        windows=windows,
        replay_ready=bool(payload["replay_ready"]),
        diversity_score=float(payload["diversity_score"]),
        window_coverage=dict(payload["window_coverage"]),
        blocking_reasons=list(payload["blocking_reasons"]),
        schema_version=int(payload.get("schema_version", REPLAY_SCHEMA_VERSION)),
    )


def load_replay_report(path: Path) -> ReplayReport:
    payload = read_json(path)
    return ReplayReport(
        generated_at=payload["generated_at"],
        bundle_ref=payload["bundle_ref"],
        window_summaries=list(payload.get("window_summaries", [])),
        selection_reasoning=dict(payload.get("selection_reasoning", {})),
        replay_ready=bool(payload["replay_ready"]),
        diversity_score=float(payload["diversity_score"]),
        window_coverage=dict(payload["window_coverage"]),
        blocking_reasons=list(payload["blocking_reasons"]),
        schema_version=int(payload.get("schema_version", REPLAY_SCHEMA_VERSION)),
    )


def load_corpus_status(path: Path) -> CorpusStatus:
    payload = read_json(path)
    required = (
        "captured_at",
        "archive_count",
        "label_counts",
        "latest_by_label",
        "missing_labels",
        "unsupported_labels",
        "fallback_windows",
        "protocol_mismatches",
        "replay_ready",
        "blocking_reasons",
        "diversity_score",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise FactoryError(f"corpus status {path} missing required keys: {', '.join(missing)}")
    return CorpusStatus(
        captured_at=payload["captured_at"],
        archive_count=int(payload["archive_count"]),
        label_counts={key: int(value) for key, value in payload["label_counts"].items()},
        latest_by_label=dict(payload["latest_by_label"]),
        missing_labels=list(payload["missing_labels"]),
        unsupported_labels=list(payload["unsupported_labels"]),
        fallback_windows=list(payload["fallback_windows"]),
        protocol_mismatches=list(payload["protocol_mismatches"]),
        replay_ready=bool(payload["replay_ready"]),
        blocking_reasons=list(payload["blocking_reasons"]),
        diversity_score=float(payload["diversity_score"]),
        next_recommended_label=payload.get("next_recommended_label"),
        heuristic_fallback_windows=list(payload.get("heuristic_fallback_windows", [])),
        schema_version=int(payload.get("schema_version", REPLAY_SCHEMA_VERSION)),
    )
