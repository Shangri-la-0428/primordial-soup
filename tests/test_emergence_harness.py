import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from emergence_harness import DEFAULT_SCENARIOS, guarded_candidate, run_harness


REPO_ROOT = Path(__file__).resolve().parents[1]


class EmergenceHarnessTest(unittest.TestCase):
    def test_guarded_candidate_passes_gate(self) -> None:
        report = run_harness(candidate=guarded_candidate())
        self.assertTrue(report.candidate.passes_gate)
        self.assertTrue(report.candidate.passes_ontology_gate)
        self.assertTrue(report.candidate.passes_mechanism_gate)
        self.assertEqual(report.candidate.metrics["new_nouns"], 0.0)
        self.assertIn("join gain", report.candidate.improvements)
        self.assertIn("poison resistance", report.candidate.improvements)
        self.assertIn("innovation preservation", report.candidate.improvements)
        self.assertIn("capability conflict governance", report.candidate.improvements)

    def test_report_exposes_frozen_ontology_contract(self) -> None:
        report = run_harness(candidate=guarded_candidate())
        self.assertEqual(
            report.boundary_contract["shared_carriers"],
            ["trace", "signal", "policy", "view"],
        )
        self.assertEqual(
            report.boundary_contract["control_dimensions"],
            [
                "scope",
                "reversibility",
                "authority_basis",
                "corroboration_scope",
                "risk_posture",
            ],
        )
        self.assertEqual(
            report.boundary_contract["evidence_states"],
            ["stable-path", "mixed-residue"],
        )

    def test_ontology_gate_rejects_new_nouns_and_invalid_carrier(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "name": "ontology-leak",
                    "concept_mapping": {
                        "carrier": "memory-lake",
                        "dimensions": ["risk_posture"],
                        "new_nouns": ["cluster"],
                    },
                },
                handle,
            )
            candidate_path = Path(handle.name)

        self.addCleanup(candidate_path.unlink, missing_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "run.py"),
                "--harness",
                "--candidate-config",
                str(candidate_path),
                "--harness-json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failures = payload["candidate"]["ontology_gate_failures"]
        self.assertTrue(any("concept mapping carrier must remain" in failure for failure in failures))
        self.assertTrue(any("candidate introduces unmappable nouns" in failure for failure in failures))
        self.assertTrue(any("candidate must not introduce new nouns" in failure for failure in failures))

    def test_wrong_signal_retention_regression_fails_gate(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "name": "sticky-wrong-signals",
                    "wrong_signal_decay": 0.98,
                    "verified_signal_decay": 0.64,
                    "promotion_threshold": 1.2,
                    "false_signal_penalty": 0.0,
                },
                handle,
            )
            candidate_path = Path(handle.name)

        self.addCleanup(candidate_path.unlink, missing_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "run.py"),
                "--harness",
                "--candidate-config",
                str(candidate_path),
                "--harness-json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failures = payload["candidate"]["mechanism_gate_failures"]
        self.assertTrue(
            any("kept wrong signals longer than verified signals" in failure for failure in failures)
        )

    def test_capability_prior_cannot_form_stable_path(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "name": "strong-prior-overreach",
                    "promotion_threshold": 1.1,
                    "capability_soft_prior_strength": 0.95,
                    "reversible_probe_bonus": 0.95,
                    "mixed_residue_bias": 0.0,
                    "novelty_protection_strength": 0.0,
                    "repeated_damage_feedback_strength": 0.5,
                },
                handle,
            )
            candidate_path = Path(handle.name)

        self.addCleanup(candidate_path.unlink, missing_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "run.py"),
                "--harness",
                "--candidate-config",
                str(candidate_path),
                "--harness-json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failures = payload["candidate"]["mechanism_gate_failures"]
        self.assertTrue(
            any("allowed capability prior to form a stable path" in failure for failure in failures)
        )

    def test_run_py_harness_json_uses_fixed_default_seeds_and_scenarios(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "run.py"),
                "--harness",
                "--harness-json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["seeds"], [42, 7, 123])
        self.assertEqual(payload["scenarios"], list(DEFAULT_SCENARIOS))
        self.assertIn("capability-conflict-falls-to-mixed-residue", payload["scenarios"])
        self.assertIn("reversible-novelty-survives-negative-feedback", payload["scenarios"])


if __name__ == "__main__":
    unittest.main()
