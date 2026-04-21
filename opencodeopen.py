#!/usr/bin/env python3
"""
opencode wrapper:
- With --openrouter: launch OpenCode routed to OpenRouter.
- Without flags: launch OpenRouter mode by default for normal run usage.
- Pass through unchanged for native management subcommands.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from open_harness_common import openrouter_target, resolve_locked_model, run_interactive

NATIVE_OVERRIDE_ENV = "OPENCODE_NATIVE_CLI"
RECURSION_GUARD_ENV = "HARNESS_OPENCODE_WRAPPER_ACTIVE"


def _wrapper_script_path() -> Path:
    return Path(__file__).resolve()


def _wrapper_cmd_path() -> Path:
    return _wrapper_script_path().with_suffix(".cmd")


def _looks_like_wrapper_shim(path: Path) -> bool:
    if not path.exists():
        return False
    if path.suffix.lower() not in {".cmd", ".bat", ".ps1", ".py"}:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False
    return "opencodeopen.py" in text and "python" in text


def _assert_not_wrapper_target(path_like: str | Path) -> None:
    candidate = Path(path_like).resolve()
    if candidate == _wrapper_script_path() or candidate == _wrapper_cmd_path() or _looks_like_wrapper_shim(candidate):
        raise RuntimeError(
            "Resolved native opencode CLI points to this wrapper shim, which would recurse. "
            f"Set {NATIVE_OVERRIDE_ENV} to the native CLI (for example %APPDATA%/npm/opencode.cmd)."
        )


def _native_opencode() -> str:
    override = os.environ.get(NATIVE_OVERRIDE_ENV, "").strip()
    if override:
        override_path = Path(override)
        if not override_path.is_absolute():
            raise RuntimeError(f"{NATIVE_OVERRIDE_ENV} must be an absolute path. Got: {override!r}")
        if not override_path.exists():
            raise RuntimeError(f"{NATIVE_OVERRIDE_ENV} path does not exist: {override}")
        _assert_not_wrapper_target(override_path)
        return str(override_path)

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "npm" / "opencode.cmd"
        if candidate.exists():
            _assert_not_wrapper_target(candidate)
            return str(candidate)

    path_hit = shutil.which("opencode")
    if path_hit:
        _assert_not_wrapper_target(path_hit)
        return path_hit

    raise RuntimeError(
        "Could not resolve native opencode CLI. "
        f"Install npm opencode or set {NATIVE_OVERRIDE_ENV} to an absolute native CLI path."
    )


def _delegate_native(argv: list[str]) -> int:
    try:
        native = _native_opencode()
    except Exception as exc:
        print(f"[opencode] {exc}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env[RECURSION_GUARD_ENV] = "1"
    cmd = [native, *argv]
    return run_interactive(cmd, env)


def _model_definition(model_id: str) -> dict:
    """Build a minimal OpenCode model definition for the given OpenRouter model slug."""
    bare = model_id.removeprefix("openrouter/")
    return {
        "id": bare,
        "name": bare,
        "family": bare.split("/")[0],
        "attachment": False,
        "reasoning": False,
        "temperature": True,
        "tool_call": True,
        "limit": {"context": 131072, "output": 16384},
    }


def _openrouter_config_content(target_base_url: str, model_id: str, api_key: str) -> str:
    bare = model_id.removeprefix("openrouter/")
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": model_id,
        "small_model": model_id,
        "enabled_providers": ["openrouter"],
        "provider": {
            "openrouter": {
                "name": "OpenRouter",
                "npm": "@ai-sdk/openai-compatible",
                "options": {
                    "baseURL": target_base_url,
                    "apiKey": api_key,
                    "headers": {
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://opencode.ai/",
                        "X-Title": "opencode",
                    },
                },
                "models": {
                    bare: _model_definition(model_id),
                },
            }
        },
    }
    return json.dumps(config, separators=(",", ":"))


def _ensure_isolated_xdg_dirs() -> tuple[str, str, str, str]:
    root = Path.home() / ".opencode-openrouter"
    data_home = root / "data"
    config_home = root / "config"
    cache_home = root / "cache"
    state_home = root / "state"
    for p in (data_home, config_home, cache_home, state_home):
        p.mkdir(parents=True, exist_ok=True)
    return (str(data_home), str(config_home), str(cache_home), str(state_home))


def main() -> int:
    if os.environ.get(RECURSION_GUARD_ENV, "").strip() == "1":
        print(
            "[opencode] recursion guard triggered: wrapper was invoked from inside itself. "
            f"Set {NATIVE_OVERRIDE_ENV} to the native CLI or fix PATH resolution.",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if not args.openrouter:
        native_passthrough = {
            "acp",
            "agent",
            "attach",
            "completion",
            "db",
            "debug",
            "export",
            "github",
            "import",
            "mcp",
            "models",
            "plugin",
            "plugins",
            "pr",
            "providers",
            "auth",
            "serve",
            "session",
            "stats",
            "uninstall",
            "upgrade",
            "web",
            "--help",
            "-h",
            "--version",
            "-v",
        }
        if passthrough and passthrough[0] in native_passthrough:
            return _delegate_native(sys.argv[1:])
        args.openrouter = True

    try:
        native_cli = _native_opencode()
        target = openrouter_target()
        model = resolve_locked_model(args.model, locked_model=target.model)
    except Exception as exc:
        print(f"[opencode] {exc}", file=sys.stderr)
        return 1

    model_arg = f"openrouter/{model}"
    cmd = [native_cli, "-m", model_arg, *passthrough]

    env = os.environ.copy()
    xdg_data_home, xdg_config_home, xdg_cache_home, xdg_state_home = _ensure_isolated_xdg_dirs()
    env["XDG_DATA_HOME"] = xdg_data_home
    env["XDG_CONFIG_HOME"] = xdg_config_home
    env["XDG_CACHE_HOME"] = xdg_cache_home
    env["XDG_STATE_HOME"] = xdg_state_home
    env[RECURSION_GUARD_ENV] = "1"
    env[target.env_key_name] = target.env_key_value
    env["OPENROUTER_API_KEY"] = target.env_key_value
    # Set OPENAI_API_KEY only for the spawned process; never as global canonical config.
    env["OPENAI_API_KEY"] = target.env_key_value
    env["OPENCODE_MODEL"] = model_arg
    env["OPENCODE_CONFIG_CONTENT"] = _openrouter_config_content(
        target_base_url=target.base_url,
        model_id=model_arg,
        api_key=target.env_key_value,
    )
    env.pop("OPENAI_BASE_URL", None)

    print(f"[opencode] provider={target.provider_name} base_url={target.base_url} model={model_arg}")
    print(f"[opencode] env_key={target.env_key_name}")
    print("[opencode] mode=forced-openrouter-config")
    print(f"[opencode] xdg_root={str(Path.home() / '.opencode-openrouter')}")
    print(f"[opencode] native_cli={native_cli}")
    print(f"[opencode] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
