from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
DEFAULT_OPENROUTER_MODELS = (
    "openai/gpt-oss-120b:free",
    "qwen/qwen3.6-plus",
    "openrouter/auto",
)
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"

HARNESS_OPENROUTER_API_KEY = "HARNESS_OPENROUTER_API_KEY"
HARNESS_OPENROUTER_BASE_URL = "HARNESS_OPENROUTER_BASE_URL"
HARNESS_OPENROUTER_MODEL = "HARNESS_OPENROUTER_MODEL"
HARNESS_OPENROUTER_MODEL_LIST = "HARNESS_OPENROUTER_MODEL_LIST"

OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
OPENROUTER_BASE_URL = "OPENROUTER_BASE_URL"
OPENROUTER_MODEL = "OPENROUTER_MODEL"
OPENROUTER_MODEL_LIST = "OPENROUTER_MODEL_LIST"


@dataclass
class LaunchTarget:
    provider_name: str
    base_url: str
    model: str
    env_key_name: str
    env_key_value: str


def _read_env_file() -> dict[str, str]:
    result: dict[str, str] = {}
    if _LOCAL_ENV_FILE.exists():
        for line in _LOCAL_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _resolve_env_value(preferred_key: str, compat_key: str, default: str = "") -> str:
    """
    Precedence order:
      1) Process env preferred key      (e.g. HARNESS_OPENROUTER_API_KEY)
      2) Process env compatibility key  (e.g. OPENROUTER_API_KEY)
      3) Local .env preferred key
      4) Local .env compatibility key
    """
    process_value = os.environ.get(preferred_key, "").strip()
    if process_value:
        return process_value
    process_compat = os.environ.get(compat_key, "").strip()
    if process_compat:
        return process_compat

    file_env = _read_env_file()
    file_value = file_env.get(preferred_key, "").strip()
    if file_value:
        return file_value
    file_compat = file_env.get(compat_key, "").strip()
    if file_compat:
        return file_compat
    return default


def _get_openrouter_key() -> str:
    return _resolve_env_value(HARNESS_OPENROUTER_API_KEY, OPENROUTER_API_KEY)


def _get_openrouter_base_url() -> str:
    return _resolve_env_value(HARNESS_OPENROUTER_BASE_URL, OPENROUTER_BASE_URL, _DEFAULT_BASE_URL)


def _get_openrouter_model() -> str:
    raw = _resolve_env_value(HARNESS_OPENROUTER_MODEL, OPENROUTER_MODEL, DEFAULT_OPENROUTER_MODEL)
    normalized = normalize_harness_model_id(raw)
    return normalized or DEFAULT_OPENROUTER_MODEL


def _split_model_list(raw: str) -> list[str]:
    models: list[str] = []
    for item in re.split(r"[\n,;]+", raw):
        normalized = normalize_harness_model_id(item)
        if normalized and normalized not in models:
            models.append(normalized)
    return models


def configured_openrouter_models() -> list[str]:
    raw = _resolve_env_value(HARNESS_OPENROUTER_MODEL_LIST, OPENROUTER_MODEL_LIST)
    models = _split_model_list(raw)
    default_model = _get_openrouter_model()
    for model in (default_model, *DEFAULT_OPENROUTER_MODELS):
        if model and model not in models:
            models.append(model)
    return models


def normalize_base_url(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        return u
    return f"{u}/v1"


def strip_v1(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        return u[:-3]
    return u


def _strip_openrouter_prefix(model: str) -> str:
    m = model.strip()
    if m.startswith("openrouter/") and "/" in m[len("openrouter/"):]:
        return m[len("openrouter/"):]
    return m


def normalize_harness_model_id(model: str) -> str:
    return _strip_openrouter_prefix(model)


def _is_openrouter_cloud_url(base_url: str) -> bool:
    return "openrouter.ai" in base_url.lower()


def validate_harness_model_id(model: str, *, base_url: str = "") -> str:
    normalized = normalize_harness_model_id(model)
    if not normalized:
        raise RuntimeError("Model must not be empty.")
    if any(ch.isspace() for ch in normalized):
        raise RuntimeError(f"Model '{model}' must not contain whitespace.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise RuntimeError(f"Model '{model}' contains control characters.")
    if _is_openrouter_cloud_url(base_url) and "/" not in normalized:
        raise RuntimeError(
            f"Model '{model}' is not a full OpenRouter model ID. "
            "Use a value like 'qwen/qwen3.6-plus'."
        )
    return normalized


def resolve_harness_model(requested_model: str = "", *, target: LaunchTarget | None = None) -> str:
    raw = requested_model if requested_model.strip() else (target.model if target else _get_openrouter_model())
    return validate_harness_model_id(raw, base_url=target.base_url if target else "")


def resolve_locked_model(requested_model: str = "", locked_model: str = "") -> str:
    """Backward-compatible wrapper name for older harness scripts."""
    raw = requested_model if requested_model.strip() else (locked_model.strip() or _get_openrouter_model())
    return validate_harness_model_id(raw)


def openrouter_target() -> LaunchTarget:
    key = _get_openrouter_key()
    if not key:
        raise RuntimeError(
            f"{HARNESS_OPENROUTER_API_KEY} (preferred) or {OPENROUTER_API_KEY} is not configured. "
            f"Set it in process env or {_LOCAL_ENV_FILE}."
        )
    return LaunchTarget(
        provider_name="openrouter",
        base_url=normalize_base_url(_get_openrouter_base_url()),
        model=_get_openrouter_model(),
        env_key_name=HARNESS_OPENROUTER_API_KEY,
        env_key_value=key,
    )


def openrouter_listing_target() -> LaunchTarget:
    return LaunchTarget(
        provider_name="openrouter",
        base_url=normalize_base_url(_get_openrouter_base_url()),
        model=_get_openrouter_model(),
        env_key_name=HARNESS_OPENROUTER_API_KEY,
        env_key_value=_get_openrouter_key(),
    )


def _resolve_windows_cmd(cmd: list[str]) -> list[str]:
    """Resolve .cmd executables on Windows — CreateProcess can't run .cmd without the shell."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return cmd
    if exe.lower().endswith(".cmd"):
        return ["cmd", "/c", exe] + cmd[1:]
    return [exe] + cmd[1:]


def run_interactive(cmd: list[str], env: dict[str, str]) -> int:
    """
    Run an interactive CLI command preserving terminal controls on Windows and Unix.
    """
    if os.name == "nt":
        cmd = _resolve_windows_cmd(cmd)
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen(cmd, env=env, shell=False, creationflags=creationflags)
        try:
            return int(proc.wait())
        except KeyboardInterrupt:
            try:
                ctrl_break = getattr(subprocess, "CTRL_BREAK_EVENT", None)
                if ctrl_break is not None:
                    proc.send_signal(ctrl_break)
                    for _ in range(20):
                        if proc.poll() is not None:
                            return int(proc.returncode)
                        time.sleep(0.1)
            except Exception:
                pass
            try:
                proc.terminate()
                for _ in range(20):
                    if proc.poll() is not None:
                        return int(proc.returncode)
                    time.sleep(0.1)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
            return 130

    os.execvpe(cmd[0], cmd, env)
    return 0
