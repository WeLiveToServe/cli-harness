#!/usr/bin/env python3
"""
codexopen: Launch Codex routed to OpenRouter.

This wrapper enforces OpenRouter compatibility mode by disabling Codex features
that inject incompatible Responses tool payloads.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path

from open_harness_common import (
    LaunchTarget,
    configured_openrouter_models,
    openrouter_listing_target,
    openrouter_target,
    resolve_harness_model,
    run_interactive,
)

COMPAT_DISABLE_FEATURES = [
    "apps",
    "plugins",
    "personality",
    "multi_agent",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "workspace_dependencies",
]


def _with_psycho_permissions(passthrough: list[str]) -> list[str]:
    flag = "--dangerously-bypass-approvals-and-sandbox"
    if flag in passthrough:
        return passthrough
    return [*passthrough, flag]


def _build_codex_cmd(target: LaunchTarget, cwd: str, model: str, passthrough: list[str]) -> list[str]:
    provider_id = "relay"
    reasoning_effort = os.environ.get("HARNESS_CODEX_REASONING_EFFORT", "").strip()
    if not reasoning_effort and "openrouter.ai" not in target.base_url:
        reasoning_effort = "high"
    cmd = [
        "codex",
        "-c",
        f'model="{model}"',
        "-c",
        f'model_provider="{provider_id}"',
        "-c",
        f'model_providers.{provider_id}.name="{target.provider_name}"',
        "-c",
        f'model_providers.{provider_id}.base_url="{target.base_url}"',
        "-c",
        f'model_providers.{provider_id}.env_key="{target.env_key_name}"',
        "-c",
        f'model_providers.{provider_id}.wire_api="responses"',
        "-C",
        cwd,
    ]
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    for feature in COMPAT_DISABLE_FEATURES:
        cmd.extend(["--disable", feature])
    if passthrough:
        cmd.extend(passthrough)
    return cmd


def _parse_openrouter_model_ids(raw_body: bytes) -> list[str]:
    payload = json.loads(raw_body.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []

    model_ids: list[str] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if model_id and model_id not in seen:
            model_ids.append(model_id)
            seen.add(model_id)
    return model_ids


def _fetch_openrouter_model_ids(target: LaunchTarget, *, include_auth: bool) -> list[str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "cli-harness/codex-os",
    }
    if include_auth:
        headers["Authorization"] = f"Bearer {target.env_key_value}"

    request = urllib.request.Request(f"{target.base_url.rstrip('/')}/models", headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        return _parse_openrouter_model_ids(response.read())


def list_openrouter_model_ids(target: LaunchTarget) -> tuple[list[str], str]:
    errors: list[str] = []
    attempts = [True, False] if target.env_key_value else [False]

    for include_auth in attempts:
        try:
            model_ids = _fetch_openrouter_model_ids(target, include_auth=include_auth)
        except urllib.error.HTTPError as exc:
            auth_note = "with auth" if include_auth else "without auth"
            errors.append(f"{auth_note}: HTTP {exc.code}")
            continue
        except Exception as exc:
            auth_note = "with auth" if include_auth else "without auth"
            errors.append(f"{auth_note}: {exc.__class__.__name__}")
            continue

        if model_ids:
            source = "openrouter"
            if not include_auth:
                source = "openrouter unauthenticated"
            return model_ids, source
        errors.append("remote returned no model IDs")

    fallback = configured_openrouter_models()
    detail = "; ".join(errors) if errors else "remote unavailable"
    return fallback, f"configured fallback ({detail})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Codex routed to OpenRouter/local GPU.")
    parser.add_argument(
        "--model",
        default="",
        metavar="MODEL_ID",
        help="Model ID to launch. Use a full OpenRouter model ID for OpenRouter cloud.",
    )
    parser.add_argument("--list-models", action="store_true", help="Print available model IDs, one per line.")
    parser.add_argument(
        "--psycho",
        action="store_true",
        help="Shortcut for --dangerously-bypass-approvals-and-sandbox.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved target and Codex command without launching.",
    )
    args, passthrough = parser.parse_known_args()

    if args.list_models:
        target = openrouter_listing_target()
        model_ids, source = list_openrouter_model_ids(target)
        print(f"[codex-os] model_source={source} count={len(model_ids)}", file=sys.stderr)
        for model_id in model_ids:
            print(model_id)
        return 0

    try:
        target = openrouter_target()
        model = resolve_harness_model(args.model, target=target)
    except Exception as exc:
        print(f"[codex-os] {exc}", file=sys.stderr)
        return 1

    if args.psycho:
        passthrough = _with_psycho_permissions(passthrough)

    cwd = str(Path.cwd())
    cmd = _build_codex_cmd(target, cwd, model, passthrough)

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value

    print(f"[codex-os] provider={target.provider_name} base_url={target.base_url} model={model}", file=sys.stderr)
    print(f"[codex-os] env_key={target.env_key_name}", file=sys.stderr)
    print(f"[codex-os] compat_disables={','.join(COMPAT_DISABLE_FEATURES)}", file=sys.stderr)
    if args.psycho:
        print("[codex-os] psycho=--dangerously-bypass-approvals-and-sandbox", file=sys.stderr)
    print(f"[codex-os] cmd={' '.join(shlex.quote(c) for c in cmd)}", file=sys.stderr)

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
