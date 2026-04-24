from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import claudeopen
import codexopen
import open_harness_common as common
import opencodeopen
import qwenopen


class HarnessCommonTests(unittest.TestCase):
    def test_model_normalization_preserves_openrouter_auto(self) -> None:
        cases = {
            "openrouter/qwen/qwen3.6-plus": "qwen/qwen3.6-plus",
            "openrouter/auto": "openrouter/auto",
            "qwen/qwen3.6-plus": "qwen/qwen3.6-plus",
            "gpt-oss-120b": "gpt-oss-120b",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(common.normalize_harness_model_id(raw), expected)

    def test_openrouter_cloud_requires_full_model_id(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "full OpenRouter model ID"):
            common.validate_harness_model_id("qwen", base_url="https://openrouter.ai/api/v1")

        self.assertEqual(
            common.validate_harness_model_id("gpt-oss-120b", base_url="http://127.0.0.1:18000/v1"),
            "gpt-oss-120b",
        )

    def test_openrouter_target_env_precedence(self) -> None:
        keys = [
            common.HARNESS_OPENROUTER_API_KEY,
            common.HARNESS_OPENROUTER_BASE_URL,
            common.HARNESS_OPENROUTER_MODEL,
            common.OPENROUTER_API_KEY,
            common.OPENROUTER_BASE_URL,
            common.OPENROUTER_MODEL,
        ]
        env = {
            common.HARNESS_OPENROUTER_API_KEY: "harness-key",
            common.HARNESS_OPENROUTER_BASE_URL: "http://127.0.0.1:18000",
            common.HARNESS_OPENROUTER_MODEL: "gpt-oss-120b",
            common.OPENROUTER_API_KEY: "compat-key",
            common.OPENROUTER_BASE_URL: "https://openrouter.ai/api/v1",
            common.OPENROUTER_MODEL: "qwen/qwen3.6-plus",
        }
        with mock.patch.dict(os.environ, {k: "" for k in keys}, clear=False):
            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch.object(common, "_read_env_file", return_value={}):
                    target = common.openrouter_target()

        self.assertEqual(target.env_key_value, "harness-key")
        self.assertEqual(target.base_url, "http://127.0.0.1:18000/v1")
        self.assertEqual(target.model, "gpt-oss-120b")


class PsychoFlagTests(unittest.TestCase):
    def test_codex_psycho_adds_bypass_flag_once(self) -> None:
        flag = "--dangerously-bypass-approvals-and-sandbox"
        self.assertEqual(codexopen._with_psycho_permissions(["exec"]), ["exec", flag])
        self.assertEqual(codexopen._with_psycho_permissions(["exec", flag]), ["exec", flag])

    def test_claude_psycho_overrides_permission_mode(self) -> None:
        self.assertEqual(
            claudeopen._with_psycho_permissions(["-p", "x", "--permission-mode", "default"]),
            ["-p", "x", "--permission-mode", "bypassPermissions", "--dangerously-skip-permissions"],
        )

    def test_qwen_psycho_overrides_approval_mode(self) -> None:
        self.assertEqual(
            qwenopen._with_psycho_permissions(["--prompt", "x", "--yolo"]),
            ["--prompt", "x", "--approval-mode", "yolo"],
        )

    def test_opencode_psycho_adds_skip_permissions_once(self) -> None:
        flag = "--dangerously-skip-permissions"
        self.assertEqual(opencodeopen._with_psycho_permissions(["run", "x"]), ["run", "x", flag])
        self.assertEqual(opencodeopen._with_psycho_permissions(["run", "x", flag]), ["run", "x", flag])


class OpenCodeTests(unittest.TestCase):
    def test_opencode_model_arg_does_not_double_prefix_openrouter_auto(self) -> None:
        self.assertEqual(opencodeopen._opencode_model_arg("openrouter/auto"), "openrouter/auto")
        self.assertEqual(opencodeopen._opencode_model_arg("qwen/qwen3.6-plus"), "openrouter/qwen/qwen3.6-plus")
        self.assertEqual(opencodeopen._opencode_model_arg("gpt-oss-120b"), "openrouter/gpt-oss-120b")

    def test_opencode_config_uses_single_model_prefix(self) -> None:
        payload = json.loads(
            opencodeopen._openrouter_config_content(
                "https://openrouter.ai/api/v1",
                "openrouter/auto",
                "test-key",
            )
        )
        self.assertEqual(payload["model"], "openrouter/auto")
        self.assertIn("auto", payload["provider"]["openrouter"]["models"])


if __name__ == "__main__":
    unittest.main()
