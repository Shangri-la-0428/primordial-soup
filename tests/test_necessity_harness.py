import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import run
from necessity import (
    DEFAULT_NECESSITY_CLAIMS,
    NECESSITY_STACKS,
    run_necessity_suite,
)
from necessity.runner import evaluate_claim_outcome, evaluate_scenario


class NecessityScenarioTest(unittest.TestCase):
    def test_fixed_policy_degrades_after_regime_shift(self) -> None:
        static_metrics = evaluate_scenario("static-baseline", stack_name="fixed-policy")
        regime_metrics = evaluate_scenario("regime-shift", stack_name="fixed-policy")

        self.assertLess(static_metrics["adaptation_lag"], regime_metrics["adaptation_lag"])
        self.assertGreater(
            static_metrics["post_shift_survival"],
            regime_metrics["post_shift_survival"] + 0.50,
        )

    def test_shared_traces_increase_memory_leverage(self) -> None:
        control_metrics = evaluate_scenario(
            "memory-timescale-split",
            stack_name="fixed-policy + private state",
        )
        open_metrics = evaluate_scenario(
            "memory-timescale-split",
            stack_name="fixed-policy + shared traces",
        )

        self.assertGreater(
            open_metrics["memory_leverage"],
            control_metrics["memory_leverage"] + 0.18,
        )
        self.assertGreater(
            open_metrics["post_shift_survival"],
            control_metrics["post_shift_survival"],
        )

    def test_heredity_improves_recovery_slope(self) -> None:
        control_metrics = evaluate_scenario(
            "memory-timescale-split",
            stack_name="fixed-policy + shared traces",
        )
        open_metrics = evaluate_scenario(
            "memory-timescale-split",
            stack_name="fixed-policy + shared traces + heredity",
        )

        self.assertGreater(
            open_metrics["recovery_slope"],
            control_metrics["recovery_slope"] + 0.08,
        )
        self.assertLess(
            open_metrics["adaptation_lag"],
            control_metrics["adaptation_lag"],
        )

    def test_heterogeneity_governance_outperforms_fixed_organization(self) -> None:
        control_metrics = evaluate_scenario(
            "heterogeneous-brains",
            stack_name="fixed-policy + shared traces + heredity",
        )
        open_metrics = evaluate_scenario(
            "heterogeneous-brains",
            stack_name="shared traces + heredity + selection pressure",
        )

        self.assertGreater(
            open_metrics["heterogeneity_absorption"],
            control_metrics["heterogeneity_absorption"] + 0.20,
        )
        self.assertGreater(
            open_metrics["organization_advantage"],
            control_metrics["organization_advantage"] + 0.10,
        )


class NecessityClaimTest(unittest.TestCase):
    def test_default_necessity_suite_holds(self) -> None:
        report = run_necessity_suite()

        self.assertEqual(len(report.claims), 4)
        self.assertTrue(report.scenario_results)
        self.assertTrue(all(result.necessity_holds for result in report.scenario_results))

    def test_identical_metrics_do_not_prove_necessity(self) -> None:
        sample_metrics = evaluate_scenario("regime-shift", stack_name="fixed-policy")
        for claim in DEFAULT_NECESSITY_CLAIMS:
            scenario = {
                "C1": "regime-shift",
                "C2": "memory-timescale-split",
                "C3": "memory-timescale-split",
                "C4": "heterogeneous-brains",
            }[claim.id]
            self.assertFalse(
                evaluate_claim_outcome(
                    claim,
                    scenario=scenario,
                    control_metrics=sample_metrics,
                    open_metrics=sample_metrics,
                )
            )

    def test_necessity_stacks_stay_minimal(self) -> None:
        self.assertEqual(
            set(NECESSITY_STACKS.keys()),
            {
                "fixed-policy",
                "fixed-policy + private state",
                "fixed-policy + shared traces",
                "fixed-policy + shared traces + heredity",
                "shared traces + heredity + selection pressure",
            },
        )


class NecessityCliTest(unittest.TestCase):
    def test_necessity_cli_outputs_json(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run.main(["--necessity", "--necessity-json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(len(payload["claims"]), 4)
        self.assertTrue(all(item["necessity_holds"] for item in payload["scenario_results"]))

    def test_necessity_path_does_not_trigger_model_profile_resolution(self) -> None:
        with patch(
            "run.resolve_llm_config",
            side_effect=AssertionError("necessity suite should not initialize model lane"),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = run.main(["--necessity", "--necessity-json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("conclusions", payload)

