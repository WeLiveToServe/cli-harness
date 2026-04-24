#!/usr/bin/env python3
"""
qwen wrapper:
- With --openrouter/--activegpu: launch Qwen CLI with OpenAI-compatible endpoint wiring.
- Without those flags: pass through to the native qwen CLI unchanged.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import openrouter_target, resolve_harness_model, run_interactive


def _native_qwen() -> str:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "npm" / "qwen.cmd"
        if candidate.exists():
            return str(candidate)
    return "qwen"


def _delegate_native(argv: list[str]) -> int:
    cmd = [_native_qwen(), *argv]
    return run_interactive(cmd, os.environ.copy())


def _with_psycho_permissions(passthrough: list[str]) -> list[str]:
    filtered: list[str] = []
    skip_next = False
    for item in passthrough:
        if skip_next:
            skip_next = False
            continue
        if item == "--approval-mode":
            skip_next = True
            continue
        if item.startswith("--approval-mode="):
            continue
        if item in {"--yolo", "-y"}:
            continue
        filtered.append(item)
    return [*filtered, "--approval-mode", "yolo"]


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--psycho", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if args.psycho:
        args.openrouter = True

    if not args.openrouter:
        native_passthrough = {"mcp", "extensions", "auth", "hooks", "hook", "channel", "--help", "-h", "--version", "-v"}
        if passthrough and passthrough[0] in native_passthrough:
            return _delegate_native(sys.argv[1:])
        args.openrouter = True

    try:
        target = openrouter_target()
        model = resolve_harness_model(args.model, target=target)
    except Exception as exc:
        print(f"[qwen] {exc}", file=sys.stderr)
        return 1

    if args.psycho:
        passthrough = _with_psycho_permissions(passthrough)

    cmd = [
        _native_qwen(),
        "--auth-type",
        "openai",
        "--openai-api-key",
        target.env_key_value,
        "--openai-base-url",
        target.base_url,
        "--model",
        model,
        *passthrough,
    ]
    cmd_redacted = cmd.copy()
    try:
        key_idx = cmd_redacted.index("--openai-api-key")
        if key_idx + 1 < len(cmd_redacted):
            cmd_redacted[key_idx + 1] = "***REDACTED***"
    except ValueError:
        pass

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value
    env["OPENAI_API_KEY"] = target.env_key_value
    env["OPENAI_BASE_URL"] = target.base_url
    # Avoid stale shell-level model var causing invalid model resolution in native qwen config.
    env["OPENROUTER_MODEL_ID"] = model

    print(f"[qwen] provider={target.provider_name} base_url={target.base_url} model={model}", file=sys.stderr)
    print("[qwen] env_key=OPENAI_API_KEY", file=sys.stderr)
    if args.psycho:
        print("[qwen] psycho=--approval-mode yolo", file=sys.stderr)
    print(f"[qwen] cmd={' '.join(shlex.quote(c) for c in cmd_redacted)}", file=sys.stderr)

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
