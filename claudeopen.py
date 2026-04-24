#!/usr/bin/env python3
"""
claudeopen: Launch Claude Code CLI routed to OpenRouter.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import openrouter_target, resolve_harness_model, run_interactive, strip_v1


def _with_psycho_permissions(passthrough: list[str]) -> list[str]:
    filtered: list[str] = []
    skip_next = False
    for item in passthrough:
        if skip_next:
            skip_next = False
            continue
        if item == "--permission-mode":
            skip_next = True
            continue
        if item.startswith("--permission-mode="):
            continue
        if item == "--dangerously-skip-permissions":
            continue
        filtered.append(item)
    return [*filtered, "--permission-mode", "bypassPermissions", "--dangerously-skip-permissions"]


def _build_cmd(cwd: str, model: str, passthrough: list[str]) -> list[str]:
    cmd = ["claude", "--model", model, "--add-dir", cwd]
    if passthrough:
        cmd.extend(passthrough)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Claude Code against OpenRouter.")
    parser.add_argument(
        "--model",
        default="",
        metavar="MODEL_ID",
        help="Model ID to launch. Use a full OpenRouter model ID for OpenRouter cloud.",
    )
    parser.add_argument(
        "--psycho",
        action="store_true",
        help="Shortcut for --permission-mode bypassPermissions --dangerously-skip-permissions.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print resolved target and command without launching.")
    args, passthrough = parser.parse_known_args()

    try:
        target = openrouter_target()
        model = resolve_harness_model(args.model, target=target)
    except Exception as exc:
        print(f"[claude-os] {exc}", file=sys.stderr)
        return 1

    if args.psycho:
        passthrough = _with_psycho_permissions(passthrough)

    cwd = str(Path.cwd())
    cmd = _build_cmd(cwd, model, passthrough)

    env = os.environ.copy()
    # Isolate from the user's claude.ai login. Without this, the stored OAuth
    # token from `claude /login` takes precedence over ANTHROPIC_API_KEY and
    # the OpenRouter routing is ignored.
    isolated_config = str(Path.home() / ".claude-openrouter")
    Path(isolated_config).mkdir(parents=True, exist_ok=True)
    env["CLAUDE_CONFIG_DIR"] = isolated_config
    env["ANTHROPIC_API_KEY"] = target.env_key_value
    # Claude expects Anthropic-compatible root (without /v1).
    env["ANTHROPIC_BASE_URL"] = strip_v1(target.base_url)
    # Bypass Claude Code's hardcoded Anthropic-model allowlist.
    env["ANTHROPIC_CUSTOM_MODEL_OPTION"] = model
    env["ANTHROPIC_CUSTOM_MODEL_OPTION_NAME"] = f"OpenRouter: {model}"

    print(f"[claude-os] provider={target.provider_name} base_url={env['ANTHROPIC_BASE_URL']} model={model}", file=sys.stderr)
    print(f"[claude-os] config_dir={isolated_config} (isolated from claude.ai login)", file=sys.stderr)
    print("[claude-os] env_key=ANTHROPIC_API_KEY (set to OpenRouter key)", file=sys.stderr)
    if args.psycho:
        print("[claude-os] psycho=--permission-mode bypassPermissions --dangerously-skip-permissions", file=sys.stderr)
    print(f"[claude-os] cmd={' '.join(shlex.quote(c) for c in cmd)}", file=sys.stderr)

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
