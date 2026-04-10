import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run as run_entry
from admission_factory import (
    build_calibration_profile,
    build_harness_baseline_snapshot,
    build_psyche_baseline_snapshot,
    build_replay_bundle,
    build_thronglets_baseline_snapshot,
    run_candidate_matrix,
    write_baseline_artifacts,
)
from emergence_harness import guarded_candidate, run_harness


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _prepare_lab_root(lab_root: Path) -> None:
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
    write_baseline_artifacts(lab_root, harness_snapshot, psyche_snapshot, thronglets_snapshot)
    (lab_root / "candidates").mkdir(parents=True, exist_ok=True)
    (lab_root / "candidates" / "guarded-emergence-v2.json").write_text(
        json.dumps(
            {
                "id": "guarded-emergence-v2",
                "summary": "baseline guarded candidate",
                "concept_mapping": {
                    "carrier": "trace",
                    "dimensions": ["risk_posture", "reversibility", "authority_basis"],
                    "public_surface_change": False,
                    "new_nouns": [],
                },
                "overrides": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class ArchitectureBoundaryTest(unittest.TestCase):
    def test_harness_package_does_not_import_admission(self) -> None:
        for path in (REPO_ROOT / "harness").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("from admission", text, path.name)
            self.assertNotIn("import admission", text, path.name)

    def test_admission_package_does_not_import_model_lane(self) -> None:
        for path in (REPO_ROOT / "admission").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("from model_lane", text, path.name)
            self.assertNotIn("import model_lane", text, path.name)

    def test_facade_modules_remain_importable(self) -> None:
        import admission_factory
        import emergence_harness

        self.assertTrue(hasattr(admission_factory, "run_candidate_matrix"))
        self.assertTrue(hasattr(admission_factory, "build_replay_bundle"))
        self.assertTrue(hasattr(emergence_harness, "run_harness"))
        self.assertTrue(hasattr(emergence_harness, "guarded_candidate"))

    def test_run_harness_mode_does_not_initialize_model_profiles(self) -> None:
        with patch.object(run_entry, "resolve_llm_config", side_effect=AssertionError("should not initialize model lane")):
            with redirect_stdout(io.StringIO()):
                exit_code = run_entry.main(["--harness", "--harness-json"])
        self.assertEqual(exit_code, 0)

    def test_artifact_key_shapes_remain_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "lab"
            _prepare_lab_root(lab_root)
            build_calibration_profile(lab_root=lab_root)
            build_replay_bundle(lab_root=lab_root)
            manifest = run_candidate_matrix(lab_root=lab_root)

            baseline_index = json.loads((lab_root / "baselines" / "index.json").read_text(encoding="utf-8"))
            replay_bundle = json.loads((lab_root / "replay" / "replay.bundle.json").read_text(encoding="utf-8"))
            corpus_status = json.loads((lab_root / "replay" / "corpus.status.json").read_text(encoding="utf-8"))
            manifest_payload = json.loads((lab_root / "results" / "promotion_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(
                set(baseline_index.keys()),
                {
                    "schema_version",
                    "captured_at",
                    "latest_snapshot_id",
                    "capture_label",
                    "capture_note",
                    "capture_origin",
                    "baseline_refs",
                    "archive_refs",
                    "boundary_contract",
                    "stack_signals",
                    "protocol_eval",
                    "contract_checks",
                    "calibration_refs",
                },
            )
            self.assertEqual(
                set(replay_bundle.keys()),
                {
                    "bundle_id",
                    "generated_at",
                    "snapshot_refs",
                    "windows",
                    "replay_ready",
                    "diversity_score",
                    "window_coverage",
                    "blocking_reasons",
                    "schema_version",
                },
            )
            self.assertEqual(
                set(corpus_status.keys()),
                {
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
                    "next_recommended_label",
                    "heuristic_fallback_windows",
                    "schema_version",
                },
            )
            self.assertEqual(
                set(manifest_payload.keys()),
                {
                    "generated_at",
                    "baseline_refs",
                    "evaluated_candidates",
                    "promotable_candidates",
                    "calibration_profile_ref",
                    "baseline_snapshot_ref",
                    "gated_under_calibration",
                    "replay_bundle_ref",
                    "replay_ready",
                    "replay_blocking_reasons",
                    "latest_snapshot_ref",
                    "gated_under_replay",
                    "schema_version",
                },
            )
            self.assertFalse(manifest.promotable_candidates)
            self.assertFalse(manifest_payload["replay_ready"])
