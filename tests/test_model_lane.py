import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run
from model_lane import (
    LLMConfig,
    ModelProfile,
    check_model_profile,
    get_transport_adapter,
    load_profile_registry,
    resolve_llm_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import run_model_benchmark  # noqa: E402


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _fake_urlopen(request, timeout=15):  # noqa: ANN001
    headers = {key.lower(): value for key, value in request.header_items()}
    if "authorization" in headers:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"action":"REST","target":[0,0]}',
                    }
                }
            ]
        }
        return _FakeHTTPResponse(payload)
    payload = {
        "content": [
            {
                "text": '{"action":"REST","target":[0,0]}',
            }
        ]
    }
    return _FakeHTTPResponse(payload)


class ModelLaneUnitTest(unittest.TestCase):
    def test_anthropic_transport_builds_request_and_parses_response(self) -> None:
        config = LLMConfig(
            profile_id="test-anthropic",
            provider="test-provider",
            transport="anthropic_messages",
            api_url="https://example.test/v1/messages",
            api_key="secret",
            model="kimi-test",
            max_tokens=16,
            max_workers=2,
        )
        adapter = get_transport_adapter("anthropic_messages")
        request = adapter.build_request(config, "hello")
        body = json.loads(request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in request.header_items()}

        self.assertEqual(body["model"], "kimi-test")
        self.assertEqual(body["messages"][0]["content"], "hello")
        self.assertEqual(headers["x-api-key"], "secret")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(
            adapter.parse_response({"content": [{"text": "ok"}]}),
            "ok",
        )

    def test_openai_transport_builds_request_and_parses_response(self) -> None:
        config = LLMConfig(
            profile_id="test-openai",
            provider="test-provider",
            transport="openai_chat_completions",
            api_url="https://example.test/v1/chat/completions",
            api_key="secret",
            model="gpt-test",
            max_tokens=32,
            max_workers=2,
        )
        adapter = get_transport_adapter("openai_chat_completions")
        request = adapter.build_request(config, "hello")
        body = json.loads(request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in request.header_items()}

        self.assertEqual(body["model"], "gpt-test")
        self.assertEqual(body["messages"][0]["content"], "hello")
        self.assertEqual(headers["authorization"], "Bearer secret")
        self.assertEqual(
            adapter.parse_response({"choices": [{"message": {"content": "ok"}}]}),
            "ok",
        )

    def test_profile_loading_applies_cli_override_precedence(self) -> None:
        config = resolve_llm_config(
            profile_id="openai-compatible",
            transport="anthropic_messages",
            api_url="https://override.test/v1/messages",
            api_key="override-key",
            model="override-model",
            max_workers=9,
        )

        self.assertEqual(config.profile_id, "openai-compatible")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.transport, "anthropic_messages")
        self.assertEqual(config.api_url, "https://override.test/v1/messages")
        self.assertEqual(config.api_key, "override-key")
        self.assertEqual(config.model, "override-model")
        self.assertEqual(config.max_workers, 9)

    def test_profile_registry_loads_from_json_config(self) -> None:
        default_profile_id, profiles = load_profile_registry()
        self.assertEqual(default_profile_id, "kimi")
        self.assertIn("kimi", profiles)
        self.assertEqual(profiles["kimi"].provider, "kimi")
        self.assertEqual(profiles["openai-compatible"].transport, "openai_chat_completions")

    def test_missing_key_invalid_transport_and_unknown_profile_raise(self) -> None:
        with self.assertRaises(ValueError):
            resolve_llm_config(profile_id="does-not-exist")

        with self.assertRaises(ValueError):
            resolve_llm_config(profile_id="kimi", transport="bogus-transport")

        with self.assertRaises(ValueError):
            resolve_llm_config(
                profile_id="missing-key",
                profiles={
                    "missing-key": ModelProfile(
                        profile_id="missing-key",
                        provider="test-provider",
                        transport="openai_chat_completions",
                        api_url="https://example.test/v1/chat/completions",
                        model="missing-key-model",
                    )
                },
            )

    def test_kimi_requires_kimi_api_key_and_does_not_fallback_to_anthropic(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fallback-key"}, clear=True), patch(
            "model_lane._launchctl_getenv", return_value=None
        ):
            with self.assertRaises(ValueError):
                resolve_llm_config(
                    profile_id="kimi",
                    profiles={
                        "kimi": ModelProfile(
                            profile_id="kimi",
                            provider="kimi",
                            transport="anthropic_messages",
                            api_url="https://example.test/v1/messages",
                            model="kimi-test",
                            api_key_env="KIMI_API_KEY",
                        )
                    },
                )

    def test_check_model_profile_reports_ready_when_launchctl_has_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "model_lane._launchctl_getenv",
            side_effect=lambda name: "launchctl-key" if name == "KIMI_API_KEY" else None,
        ):
            report = check_model_profile(
                "kimi",
                registry_path=REPO_ROOT / "config" / "model_profiles.json",
            )

        self.assertTrue(report["ready"])
        self.assertFalse(report["process_env_present"])
        self.assertTrue(report["launchctl_env_present"])
        self.assertEqual(report["resolved_source"], "launchctl_env")

    def test_check_model_profile_reports_missing_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "model_lane._launchctl_getenv", return_value=None
        ):
            report = check_model_profile(
                "kimi",
                registry_path=REPO_ROOT / "config" / "model_profiles.json",
            )

        self.assertFalse(report["ready"])
        self.assertEqual(report["api_key_env"], "KIMI_API_KEY")
        self.assertIsNone(report["resolved_source"])

    def test_list_model_profiles_cli_outputs_registry_entries(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run.main(["--list-model-profiles"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(any(item["profile_id"] == "kimi" for item in payload))
        self.assertTrue(any(item["default"] for item in payload))

    def test_check_model_profile_cli_returns_nonzero_when_missing(self) -> None:
        stdout = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch(
            "model_lane._launchctl_getenv", return_value=None
        ):
            with redirect_stdout(stdout):
                exit_code = run.main(["--check-model-profile", "kimi"])

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ready"])

    def test_harness_path_does_not_trigger_model_profile_resolution(self) -> None:
        with patch("run.resolve_llm_config", side_effect=AssertionError("should not resolve profile")):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = run.main(["--harness", "--harness-json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("candidate", payload)

    def test_check_model_profile_cli_returns_ready_without_printing_secret(self) -> None:
        stdout = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch(
            "model_lane._launchctl_getenv",
            side_effect=lambda name: "launchctl-secret-value" if name == "KIMI_API_KEY" else None,
        ):
            with redirect_stdout(stdout):
                exit_code = run.main(["--check-model-profile", "kimi"])

        self.assertEqual(exit_code, 0)
        rendered = stdout.getvalue()
        payload = json.loads(rendered)
        self.assertTrue(payload["ready"])
        self.assertNotIn("launchctl-secret-value", rendered)


class ModelLaneIntegrationTest(unittest.TestCase):
    def test_llm_run_still_works_with_fake_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "soup.urllib.request.urlopen", _fake_urlopen
        ):
            with redirect_stdout(io.StringIO()):
                exit_code = run.main(
                    [
                        "--llm",
                        "--model-profile",
                        "openai-compatible",
                        "--api-key",
                        "test-key",
                        "--ticks",
                        "2",
                        "--pop",
                        "4",
                        "--print-every",
                        "10",
                        "--data-dir",
                        tmpdir,
                    ]
                )

            output_path = Path(tmpdir) / "run_llm_seed42.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            history = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(history)

    def test_benchmark_runner_writes_summary_without_touching_admission_artifacts(self) -> None:
        manifest_path = REPO_ROOT / "lab" / "results" / "promotion_manifest.json"
        manifest_before = (
            manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else None
        )

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "soup.urllib.request.urlopen", _fake_urlopen
        ):
            with redirect_stdout(io.StringIO()):
                exit_code = run_model_benchmark.main(
                    [
                        "--model-profile",
                        "kimi",
                        "--transport",
                        "openai_chat_completions",
                        "--api-url",
                        "https://example.test/v1/chat/completions",
                        "--api-key",
                        "test-key",
                        "--model",
                        "gpt-fake",
                        "--modes",
                        "llm,hybrid",
                        "--seeds",
                        "42",
                        "--ticks",
                        "2",
                        "--pop",
                        "4",
                        "--print-every",
                        "10",
                        "--output-root",
                        tmpdir,
                        "--timestamp",
                        "20260410T040000Z",
                    ]
                )

            benchmark_dir = Path(tmpdir) / "kimi" / "20260410T040000Z"
            summary_path = benchmark_dir / "summary.json"
            llm_path = benchmark_dir / "llm_seed42.json"
            hybrid_path = benchmark_dir / "hybrid_seed42.json"

            self.assertEqual(exit_code, 0)
            self.assertTrue(summary_path.exists())
            self.assertTrue(llm_path.exists())
            self.assertTrue(hybrid_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["profile_id"], "kimi")
            self.assertEqual(len(summary["runs"]), 2)
            self.assertEqual(
                sorted(run_summary["mode"] for run_summary in summary["runs"]),
                ["hybrid", "llm"],
            )
            self.assertTrue(
                all(run_summary["profile"]["transport"] == "openai_chat_completions" for run_summary in summary["runs"])
            )

        manifest_after = (
            manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else None
        )
        self.assertEqual(manifest_before, manifest_after)


if __name__ == "__main__":
    unittest.main()
