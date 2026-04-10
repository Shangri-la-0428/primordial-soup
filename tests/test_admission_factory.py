import copy
import json
import tempfile
import unittest
from pathlib import Path

from admission_factory import (
    BASELINE_FILES,
    CALIBRATABLE_KEYS,
    CalibrationProfile,
    CandidateSpec,
    ConceptMapping,
    CorpusStatus,
    FactoryError,
    ReplayBundle,
    _substrate_activity_score,
    evaluate_replay_protocol,
    build_calibration_profile,
    build_replay_bundle,
    build_harness_baseline_snapshot,
    build_psyche_baseline_snapshot,
    build_thronglets_baseline_snapshot,
    load_candidate_spec,
    probe_stack_state,
    run_candidate_matrix,
    write_baseline_artifacts,
)
from emergence_harness import guarded_candidate, run_harness


def _sample_psyche_payload() -> dict:
    return {
        "ok": True,
        "canonicalHostSurface": True,
        "externalContinuityAvailable": True,
        "overlay": {"arousal": 0.01},
        "trajectory": {"kind": None, "dimensions": [], "magnitude": 0, "description": None},
        "degradation": {
            "subjectiveStatus": "healthy",
            "delegateStatus": "healthy",
            "chemistryDeviation": 0.1,
            "predictionError": 0.01,
            "issueCount": 0,
        },
        "boundaryStress": {
            "currentBoundary": 55,
            "baselineBoundary": 55,
            "boundaryDelta": 0,
            "peakDyadicBoundaryPressure": 0.1,
            "activeDyadicRelations": 1,
        },
        "fixture": {
            "frozenIdentityPrimitives": ["principal", "account", "delegate", "session"],
            "frozenSignalKinds": ["recommend", "avoid", "watch", "info"],
            "frozenTraceTaxonomy": ["coordination", "continuity", "calibration"],
            "externalContinuity": {
                "provider": "thronglets",
                "mode": "optional",
                "version": 1,
            },
        },
    }


def _sample_thronglets_payload() -> dict:
    return {
        "project_scope": None,
        "signal_eval": {"sessions_considered": 3},
        "workspace_emergence": {
            "active_spaces_24h": 2,
            "global_positive_24h": 1,
            "global_negative_24h": 1,
            "false_signal_pressure": 0.2,
            "false_consensus_spaces_24h": 0,
            "recoverable_spaces_24h": 1,
            "cross_space_contamination_rate": 0.1,
            "space_feedback": {},
        },
        "substrate_activity": {
            "activity": "learning",
            "recent_interventions_15m": 1,
            "last_intervention_tool": "Bash",
            "last_intervention_kinds": ["watch"],
            "last_intervention_age_ms": 100,
        },
    }


def _write_candidate(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _deep_update(base: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def _prepare_lab_root(
    lab_root: Path,
    *,
    captured_at: str = "2026-04-10T00:00:00+00:00",
    psyche_overrides: dict | None = None,
    thronglets_overrides: dict | None = None,
    capture_label: str | None = None,
    capture_note: str | None = None,
    capture_origin: str | None = None,
) -> None:
    report = run_harness(candidate=guarded_candidate())
    harness_snapshot = build_harness_baseline_snapshot(
        json.loads(report.to_json()),
        "python3 run.py --harness --harness-json",
        captured_at,
    )
    psyche_snapshot = build_psyche_baseline_snapshot(
        _deep_update(_sample_psyche_payload(), psyche_overrides or {}),
        "npm run probe",
        captured_at,
    )
    thronglets_snapshot = build_thronglets_baseline_snapshot(
        _deep_update(_sample_thronglets_payload(), thronglets_overrides or {}),
        "cargo run -- --data-dir <tempdir> eval-emergence --global --hours 168 --max-sessions 10 --json",
        captured_at,
    )
    write_baseline_artifacts(
        lab_root,
        harness_snapshot,
        psyche_snapshot,
        thronglets_snapshot,
        capture_label=capture_label,
        capture_note=capture_note or (f"{capture_label} fixture capture" if capture_label and capture_label != "unlabeled" else None),
        capture_origin=capture_origin,
    )


def _prepare_replay_history(lab_root: Path) -> None:
    snapshots = [
        (
            "2026-04-10T00:00:00+00:00",
            "quiet-baseline",
            {
                "degradation": {"predictionError": 0.0, "issueCount": 0},
                "boundaryStress": {"boundaryDelta": 0.0},
            },
            {
                "workspace_emergence": {
                    "false_signal_pressure": 0.0,
                    "cross_space_contamination_rate": 0.0,
                    "recoverable_spaces_24h": 0,
                    "active_spaces_24h": 0,
                },
                "substrate_activity": {"activity": "quiet"},
            },
        ),
        (
            "2026-04-10T00:05:00+00:00",
            "continuity-stress",
            {
                "degradation": {"predictionError": 0.95, "issueCount": 4},
                "boundaryStress": {"boundaryDelta": 8.0},
            },
            {
                "workspace_emergence": {
                    "false_signal_pressure": 0.1,
                    "cross_space_contamination_rate": 0.05,
                    "recoverable_spaces_24h": 1,
                    "active_spaces_24h": 3,
                },
                "substrate_activity": {"activity": "learning"},
            },
        ),
        (
            "2026-04-10T00:10:00+00:00",
            "contamination-spike",
            {},
            {
                "workspace_emergence": {
                    "false_signal_pressure": 0.95,
                    "cross_space_contamination_rate": 0.85,
                    "recoverable_spaces_24h": 1,
                    "active_spaces_24h": 4,
                },
                "substrate_activity": {"activity": "active"},
            },
        ),
        (
            "2026-04-10T00:15:00+00:00",
            "repair-window",
            {
                "degradation": {"predictionError": 0.2, "issueCount": 1},
                "boundaryStress": {"boundaryDelta": 1.0},
            },
            {
                "workspace_emergence": {
                    "false_signal_pressure": 0.18,
                    "cross_space_contamination_rate": 0.08,
                    "recoverable_spaces_24h": 2,
                    "active_spaces_24h": 4,
                },
                "substrate_activity": {"activity": "learning"},
            },
        ),
        (
            "2026-04-10T00:20:00+00:00",
            "unlabeled",
            {
                "degradation": {"predictionError": 0.04, "issueCount": 0},
                "boundaryStress": {"boundaryDelta": 0.0},
            },
            {
                "workspace_emergence": {
                    "false_signal_pressure": 0.05,
                    "cross_space_contamination_rate": 0.02,
                    "recoverable_spaces_24h": 1,
                    "active_spaces_24h": 3,
                },
                "substrate_activity": {"activity": "learning"},
            },
        ),
    ]
    for captured_at, capture_label, psyche_overrides, thronglets_overrides in snapshots:
        _prepare_lab_root(
            lab_root,
            captured_at=captured_at,
            psyche_overrides=psyche_overrides,
            thronglets_overrides=thronglets_overrides,
            capture_label=capture_label,
            capture_origin="stack-readonly",
            capture_note=f"{capture_label} fixture capture" if capture_label != "unlabeled" else None,
        )


def _prepare_homogeneous_replay_history(lab_root: Path) -> None:
    snapshots = [
        ("2026-04-10T00:00:00+00:00", "quiet-baseline"),
        ("2026-04-10T00:05:00+00:00", "continuity-stress"),
        ("2026-04-10T00:10:00+00:00", "contamination-spike"),
    ]
    for captured_at, capture_label in snapshots:
        _prepare_lab_root(
            lab_root,
            captured_at=captured_at,
            capture_label=capture_label,
            capture_note=f"{capture_label} fixture capture",
        )


def _fake_stack_command_runner(args: list[str], cwd: Path) -> dict:
    command = " ".join(args)
    if command.endswith("run.py --harness --harness-json"):
        return json.loads(run_harness(candidate=guarded_candidate()).to_json())
    if args[:3] == ["npm", "run", "probe"]:
        return _sample_psyche_payload()
    if args[:2] == ["cargo", "run"]:
        return _sample_thronglets_payload()
    raise AssertionError(f"unexpected command: {command} @ {cwd}")


class AdmissionFactoryTest(unittest.TestCase):
    def test_replay_protocol_outputs_stable_label_support(self) -> None:
        quiet = evaluate_replay_protocol(
            {
                "boundary_fragility": 0.1,
                "false_signal_stickiness": 0.05,
                "cross_space_leach": 0.05,
                "repair_capacity": 0.0,
                "continuity_health": 0.2,
            },
            selected_label="quiet-baseline",
        )
        contamination = evaluate_replay_protocol(
            {
                "boundary_fragility": 0.3,
                "false_signal_stickiness": 0.8,
                "cross_space_leach": 0.7,
                "repair_capacity": 0.1,
                "continuity_health": 0.8,
            },
            selected_label="contamination-spike",
        )
        self.assertTrue(quiet["selected_label_supported"])
        self.assertIn("quiet-baseline", quiet["recommended_labels"])
        self.assertTrue(contamination["selected_label_supported"])
        self.assertIn("contamination-spike", contamination["recommended_labels"])

    def test_probe_stack_state_reports_supported_quiet_window(self) -> None:
        report = probe_stack_state(
            command_runner=_fake_stack_command_runner,
            capture_label="quiet-baseline",
        )

        self.assertTrue(report["contract_checks"]["passed"])
        self.assertTrue(report["protocol_eval"]["selected_label_supported"])
        self.assertIn("quiet-baseline", report["protocol_eval"]["recommended_labels"])

    def test_probe_stack_state_reports_unsupported_contamination_window(self) -> None:
        report = probe_stack_state(
            command_runner=_fake_stack_command_runner,
            capture_label="contamination-spike",
        )

        self.assertTrue(report["contract_checks"]["passed"])
        self.assertFalse(report["protocol_eval"]["selected_label_supported"])
        self.assertIn(
            "selected label 'contamination-spike' is not supported by current replay protocol evaluation",
            report["protocol_eval"]["blocking_reasons"],
        )

    def test_write_baseline_artifacts_requires_capture_note_for_labeled_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            report = run_harness(candidate=guarded_candidate())
            harness_snapshot = build_harness_baseline_snapshot(
                json.loads(report.to_json()),
                "python3 run.py --harness --harness-json",
                "2026-04-10T00:00:00+00:00",
            )
            psyche_snapshot = build_psyche_baseline_snapshot(
                _sample_psyche_payload(),
                "npm run probe",
                "2026-04-10T00:00:00+00:00",
            )
            thronglets_snapshot = build_thronglets_baseline_snapshot(
                _sample_thronglets_payload(),
                "cargo run -- --data-dir <tempdir> eval-emergence --global --hours 168 --max-sessions 10 --json",
                "2026-04-10T00:00:00+00:00",
            )
            with self.assertRaises(FactoryError):
                write_baseline_artifacts(
                    lab_root,
                    harness_snapshot,
                    psyche_snapshot,
                    thronglets_snapshot,
                    capture_label="quiet-baseline",
                    capture_note=None,
                    capture_origin="manual-guided",
                )

    def test_load_candidate_spec_parses_required_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "candidate.json"
            payload = {
                "schema_version": 1,
                "id": "guarded-emergence-v2",
                "summary": "Sample candidate",
                "concept_mapping": {
                    "carrier": "trace",
                    "dimensions": ["risk_posture"],
                    "public_surface_change": False,
                    "new_nouns": [],
                },
                "overrides": {"wrong_signal_decay": 0.7},
            }
            _write_candidate(path, payload)
            spec = load_candidate_spec(path)

        self.assertIsInstance(spec, CandidateSpec)
        self.assertEqual(spec.id, "guarded-emergence-v2")
        self.assertEqual(spec.summary, "Sample candidate")
        self.assertEqual(spec.concept_mapping, ConceptMapping(carrier="trace", dimensions=("risk_posture",)))
        self.assertEqual(spec.overrides["wrong_signal_decay"], 0.7)

    def test_write_baseline_artifacts_emits_index_and_contract_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_lab_root(
                lab_root,
                capture_label="quiet-baseline",
                capture_note="baseline capture",
                capture_origin="manual-guided",
            )
            index_path = lab_root / "baselines" / BASELINE_FILES["index"]
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertTrue(index_path.exists())
            self.assertTrue(index["contract_checks"]["passed"])
            self.assertIn("latest_snapshot_id", index)
            self.assertEqual(index["capture_label"], "quiet-baseline")
            self.assertEqual(index["capture_note"], "baseline capture")
            self.assertEqual(index["capture_origin"], "manual-guided")
            self.assertIn("protocol_eval", index)
            self.assertTrue(index["protocol_eval"]["selected_label_supported"])
            self.assertIn("harness.control", index["baseline_refs"])
            self.assertIn("psyche.probe", index["baseline_refs"])
            self.assertIn("thronglets.eval-emergence", index["baseline_refs"])
            self.assertIn(index["latest_snapshot_id"], index["archive_refs"])
            archived_index = lab_root.parent / index["archive_refs"][index["latest_snapshot_id"]]
            archived_payload = json.loads(archived_index.read_text(encoding="utf-8"))
            self.assertTrue(archived_index.exists())
            self.assertEqual(archived_payload["capture_label"], "quiet-baseline")
            self.assertEqual(archived_payload["capture_note"], "baseline capture")
            self.assertEqual(archived_payload["capture_origin"], "manual-guided")
            self.assertIn("protocol_eval", archived_payload)
            self.assertEqual(index["stack_signals"]["psyche"]["boundary_delta"], 0.0)
            self.assertEqual(index["stack_signals"]["psyche"]["prediction_error"], 0.01)
            self.assertEqual(index["stack_signals"]["thronglets"]["false_signal_pressure"], 0.2)
            self.assertEqual(index["stack_signals"]["thronglets"]["substrate_activity"], "learning")

    def test_substrate_activity_score_falls_back_to_half_for_unknown_values(self) -> None:
        self.assertEqual(_substrate_activity_score(None), 0.5)
        self.assertEqual(_substrate_activity_score("mystery"), 0.5)
        self.assertEqual(_substrate_activity_score("quiet"), 0.2)
        self.assertEqual(_substrate_activity_score("converging"), 0.8)

    def test_build_calibration_profile_maps_stack_signals_to_frozen_axes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_lab_root(lab_root)

            profile, report = build_calibration_profile(lab_root=lab_root)
            profile_path = lab_root / "baselines" / BASELINE_FILES["calibration.profile"]
            report_path = lab_root / "baselines" / BASELINE_FILES["calibration.report"]
            index = json.loads((lab_root / "baselines" / BASELINE_FILES["index"]).read_text(encoding="utf-8"))
            self.assertIsInstance(profile, CalibrationProfile)
            self.assertTrue(profile_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(
                sorted(profile.axes.keys()),
                sorted(
                    [
                        "boundary_fragility",
                        "false_signal_stickiness",
                        "cross_space_leach",
                        "repair_capacity",
                        "continuity_health",
                    ]
                ),
            )
            self.assertTrue(set(profile.harness_overrides).issubset(CALIBRATABLE_KEYS))
            self.assertEqual(report.profile_ref, "lab/baselines/calibration.profile.json")
            self.assertIn("calibration_refs", index)
            self.assertIn("calibration.profile", index["calibration_refs"])
            self.assertIn("calibration.report", index["calibration_refs"])

    def test_build_replay_bundle_is_not_ready_before_five_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_homogeneous_replay_history(lab_root)
            bundle, report, status = build_replay_bundle(lab_root=lab_root)
            self.assertFalse(bundle.replay_ready)
            self.assertFalse(report.replay_ready)
            self.assertIsInstance(status, CorpusStatus)
            self.assertIn("replay corpus needs at least 5 recent snapshots", status.blocking_reasons[0])

    def test_build_replay_bundle_selects_deterministic_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_replay_history(lab_root)
            bundle, report, status = build_replay_bundle(lab_root=lab_root)
            bundle_path = lab_root / "replay" / "replay.bundle.json"
            report_path = lab_root / "replay" / "replay.report.json"
            status_path = lab_root / "replay" / "corpus.status.json"

            self.assertIsInstance(bundle, ReplayBundle)
            self.assertTrue(bundle_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(status_path.exists())
            self.assertEqual(
                [window.name for window in bundle.windows],
                [
                    "quiet-baseline",
                    "continuity-stress",
                    "contamination-spike",
                    "repair-window",
                ],
            )
            self.assertEqual(bundle.windows[0].snapshot_id, "20260410T000000plus0000")
            self.assertEqual(bundle.windows[1].snapshot_id, "20260410T000500plus0000")
            self.assertEqual(bundle.windows[2].snapshot_id, "20260410T001000plus0000")
            self.assertEqual(bundle.windows[3].snapshot_id, "20260410T001500plus0000")
            self.assertTrue(bundle.replay_ready)
            self.assertGreater(bundle.diversity_score, 0.15)
            self.assertEqual(bundle.window_coverage["unique_snapshot_count"], 4)
            self.assertEqual(bundle.window_coverage["selection_modes"]["quiet-baseline"], "label-supported")
            self.assertEqual(bundle.blocking_reasons, [])
            self.assertTrue(
                all(set(window.harness_overrides).issubset(CALIBRATABLE_KEYS) for window in bundle.windows)
            )
            self.assertEqual(report.bundle_ref, "lab/replay/replay.bundle.json")
            self.assertTrue(report.replay_ready)
            self.assertTrue(status.replay_ready)
            self.assertEqual(status.missing_labels, [])
            self.assertEqual(status.unsupported_labels, [])
            self.assertEqual(status.fallback_windows, [])
            self.assertEqual(status.protocol_mismatches, [])
            self.assertEqual(status.label_counts["quiet-baseline"], 1)

    def test_build_replay_bundle_marks_homogeneous_archive_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_homogeneous_replay_history(lab_root)

            bundle, report, status = build_replay_bundle(lab_root=lab_root)

            self.assertFalse(bundle.replay_ready)
            self.assertLess(bundle.diversity_score, 0.15)
            self.assertEqual(bundle.window_coverage["unique_snapshot_count"], 3)
            self.assertTrue(bundle.blocking_reasons)
            self.assertFalse(report.replay_ready)
            self.assertFalse(status.replay_ready)
            self.assertIn("missing labeled replay windows", "\n".join(status.blocking_reasons))
            self.assertEqual(status.fallback_windows, ["repair-window"])

    def test_build_replay_bundle_prefers_labeled_snapshot_over_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_replay_history(lab_root)
            _prepare_lab_root(
                lab_root,
                captured_at="2026-04-10T00:25:00+00:00",
                capture_label="continuity-stress",
                capture_note="late manual stress label",
                capture_origin="manual-guided",
                psyche_overrides={
                    "degradation": {"predictionError": 0.2, "issueCount": 1},
                    "boundaryStress": {"boundaryDelta": 1.0},
                },
            )

            _bundle, report, status = build_replay_bundle(lab_root=lab_root)
            continuity = next(
                summary for summary in report.window_summaries if summary["name"] == "continuity-stress"
            )
            self.assertEqual(continuity["selection_mode"], "label-supported")
            self.assertEqual(continuity["capture_label"], "continuity-stress")
            self.assertIn("continuity-stress", status.latest_by_label)

    def test_build_replay_bundle_marks_protocol_mismatch_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_replay_history(lab_root)
            _prepare_lab_root(
                lab_root,
                captured_at="2026-04-10T00:25:00+00:00",
                capture_label="quiet-baseline",
                capture_note="forced mismatch capture",
                capture_origin="manual-guided",
                psyche_overrides={
                    "degradation": {"predictionError": 0.95, "issueCount": 4},
                    "boundaryStress": {"boundaryDelta": 8.0},
                },
                thronglets_overrides={
                    "workspace_emergence": {
                        "false_signal_pressure": 0.9,
                        "cross_space_contamination_rate": 0.8,
                        "recoverable_spaces_24h": 0,
                        "active_spaces_24h": 4,
                    },
                    "substrate_activity": {"activity": "active"},
                },
            )

            _bundle, _report, status = build_replay_bundle(lab_root=lab_root)
            self.assertFalse(status.replay_ready)
            self.assertIn("quiet-baseline", status.unsupported_labels)
            self.assertTrue(status.protocol_mismatches)

    def test_run_candidate_matrix_skips_mechanism_when_ontology_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_replay_history(lab_root)
            build_calibration_profile(lab_root=lab_root)
            build_replay_bundle(lab_root=lab_root)
            _write_candidate(
                lab_root / "candidates" / "ontology-leak.json",
                {
                    "schema_version": 1,
                    "id": "ontology-leak",
                    "summary": "Invalid ontology candidate",
                    "concept_mapping": {
                        "carrier": "memory-lake",
                        "dimensions": ["risk_posture"],
                        "public_surface_change": False,
                        "new_nouns": ["cluster"],
                    },
                    "overrides": {},
                },
            )
            _write_candidate(
                lab_root / "candidates" / "guarded-emergence-v2.json",
                {
                    "schema_version": 1,
                    "id": "guarded-emergence-v2",
                    "summary": "Valid candidate",
                    "concept_mapping": {
                        "carrier": "trace",
                        "dimensions": ["risk_posture", "reversibility", "authority_basis"],
                        "public_surface_change": False,
                        "new_nouns": [],
                    },
                    "overrides": {},
                },
            )

            calls: list[str] = []

            def fake_harness_runner(**kwargs):
                calls.append(kwargs["candidate"].name)
                return run_harness(candidate=guarded_candidate())

            run_candidate_matrix(lab_root=lab_root, harness_runner=fake_harness_runner)
            result = json.loads(
                (lab_root / "results" / "ontology-leak.json").read_text(encoding="utf-8")
            )

        self.assertEqual(calls, ["guarded-emergence-v2"])
        self.assertFalse(result["ontology_gate_passed"])
        self.assertFalse(result["mechanism_gate_passed"])
        self.assertTrue(result["gated_under_calibration"])
        self.assertTrue(result["gated_under_replay"])
        self.assertEqual(result["calibration_profile_ref"], "lab/baselines/calibration.profile.json")
        self.assertEqual(result["replay_bundle_ref"], "lab/replay/replay.bundle.json")
        self.assertIn(
            "ontology gate failed; mechanism evaluation skipped",
            result["mechanism_gate_failures"],
        )

    def test_promotion_manifest_only_collects_double_gate_passers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_replay_history(lab_root)
            samples = [
                {
                    "schema_version": 1,
                    "id": "guarded-emergence-v2",
                    "summary": "Promotable candidate",
                    "concept_mapping": {
                        "carrier": "trace",
                        "dimensions": ["risk_posture", "reversibility", "authority_basis"],
                        "public_surface_change": False,
                        "new_nouns": [],
                    },
                    "overrides": {},
                },
                {
                    "schema_version": 1,
                    "id": "replay-fragile-isolation",
                    "summary": "Passes the latest quiet calibration but regresses under contamination replay windows.",
                    "concept_mapping": {
                        "carrier": "trace",
                        "dimensions": ["risk_posture", "corroboration_scope"],
                        "public_surface_change": False,
                        "new_nouns": [],
                    },
                    "overrides": {
                        "space_isolation_strength": 0.9,
                        "cross_space_leakage": 0.08,
                        "trace_recovery_bonus": 0.2,
                        "local_repair_bias": 0.22,
                    },
                },
                {
                    "schema_version": 1,
                    "id": "ontology-leak",
                    "summary": "Ontology fail candidate",
                    "concept_mapping": {
                        "carrier": "memory-lake",
                        "dimensions": ["risk_posture"],
                        "public_surface_change": False,
                        "new_nouns": ["cluster"],
                    },
                    "overrides": {},
                },
                {
                    "schema_version": 1,
                    "id": "sticky-wrong-signals",
                    "summary": "Mechanism fail candidate",
                    "concept_mapping": {
                        "carrier": "trace",
                        "dimensions": ["risk_posture"],
                        "public_surface_change": False,
                        "new_nouns": [],
                    },
                    "overrides": {
                        "wrong_signal_decay": 0.98,
                        "verified_signal_decay": 0.64,
                        "promotion_threshold": 1.2,
                        "false_signal_penalty": 0.0,
                    },
                },
            ]
            for payload in samples:
                _write_candidate(lab_root / "candidates" / f"{payload['id']}.json", payload)

            build_calibration_profile(lab_root=lab_root)
            build_replay_bundle(lab_root=lab_root)
            manifest = run_candidate_matrix(lab_root=lab_root)
            replay_result = json.loads(
                (lab_root / "results" / "replay-fragile-isolation.json").read_text(encoding="utf-8")
            )
            ontology_result = json.loads(
                (lab_root / "results" / "ontology-leak.json").read_text(encoding="utf-8")
            )
            mechanism_result = json.loads(
                (lab_root / "results" / "sticky-wrong-signals.json").read_text(encoding="utf-8")
            )
            manifest_payload = json.loads(
                (lab_root / "results" / "promotion_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest.promotable_candidates, ["guarded-emergence-v2"])
            self.assertFalse(replay_result["promotable"])
            self.assertFalse(replay_result["replay_gate_passed"])
            self.assertTrue(replay_result["mechanism_gate_passed"])
            self.assertTrue(replay_result["gated_under_replay"])
            self.assertEqual(replay_result["replay_bundle_ref"], "lab/replay/replay.bundle.json")
            self.assertFalse(ontology_result["promotable"])
            self.assertFalse(mechanism_result["promotable"])
            self.assertTrue(manifest_payload["gated_under_calibration"])
            self.assertTrue(manifest_payload["gated_under_replay"])
            self.assertEqual(
                manifest_payload["calibration_profile_ref"],
                "lab/baselines/calibration.profile.json",
            )
            self.assertEqual(manifest_payload["baseline_snapshot_ref"], "lab/baselines/index.json")
            self.assertEqual(manifest_payload["latest_snapshot_ref"], "lab/baselines/index.json")
            self.assertEqual(manifest_payload["replay_bundle_ref"], "lab/replay/replay.bundle.json")
            self.assertTrue((lab_root / "results" / "promotion_manifest.json").exists())

    def test_promotion_manifest_blocks_candidates_when_replay_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_homogeneous_replay_history(lab_root)
            _write_candidate(
                lab_root / "candidates" / "guarded-emergence-v2.json",
                {
                    "schema_version": 1,
                    "id": "guarded-emergence-v2",
                    "summary": "Promotable only when replay corpus is ready",
                    "concept_mapping": {
                        "carrier": "trace",
                        "dimensions": ["risk_posture", "reversibility", "authority_basis"],
                        "public_surface_change": False,
                        "new_nouns": [],
                    },
                    "overrides": {},
                },
            )

            build_calibration_profile(lab_root=lab_root)
            build_replay_bundle(lab_root=lab_root)
            manifest = run_candidate_matrix(lab_root=lab_root)
            result = json.loads(
                (lab_root / "results" / "guarded-emergence-v2.json").read_text(encoding="utf-8")
            )
            manifest_payload = json.loads(
                (lab_root / "results" / "promotion_manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(manifest.promotable_candidates, [])
            self.assertTrue(result["mechanism_gate_passed"])
            self.assertFalse(result["replay_ready"])
            self.assertFalse(result["replay_gate_passed"])
            self.assertFalse(result["promotable"])
            self.assertTrue(result["replay_blocking_reasons"])
            self.assertFalse(manifest_payload["replay_ready"])
            self.assertTrue(manifest_payload["replay_blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
