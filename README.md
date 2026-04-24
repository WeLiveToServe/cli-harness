# CLI Harness Wrappers

This repository is the source of truth for local harness launcher wrappers.

## Commands

Canonical wrapper commands:

```powershell
C:\Users\keith\dev\cli-harness\codex-os.cmd
C:\Users\keith\dev\cli-harness\claude-os.cmd
C:\Users\keith\dev\cli-harness\opencode.cmd
C:\Users\keith\dev\cli-harness\qwen.cmd
```

Legacy aliases `codexopen.cmd` and `claudeopen.cmd` are still present for
older scripts, but new usage should prefer `codex-os.cmd` and `claude-os.cmd`.

## Psycho Mode

Every wrapper accepts `--psycho` as a local convenience alias for that harness's
maximum-permission mode:

| Wrapper | Expands to |
| --- | --- |
| `codex-os` | `--dangerously-bypass-approvals-and-sandbox` |
| `claude-os` | `--permission-mode bypassPermissions --dangerously-skip-permissions` |
| `opencode` | `--dangerously-skip-permissions` |
| `qwen` | `--approval-mode yolo` |

Examples:

```powershell
codex-os --psycho exec --skip-git-repo-check "Reply with OK"
claude-os --psycho -p "Reply with OK"
opencode --psycho run "Reply with OK"
qwen --psycho --prompt "Reply with OK"
```

## Model Selection

For OpenRouter cloud, pass full OpenRouter model IDs:

```powershell
codex-os --list-models
codex-os --model qwen/qwen3.6-plus
qwen --model openai/gpt-oss-120b:free --prompt "Reply with OK"
```

For local GPU endpoints, process-scoped `HARNESS_OPENROUTER_MODEL` can still be
a served model name such as `gpt-oss-120b`.

## OpenCode Deterministic Launch

During repair and validation, run OpenCode from this repo only:

```powershell
C:\Users\keith\dev\cli-harness\opencode.cmd --psycho run "Reply with OK" --pure
```

Do not use bare `opencode` during repair because shell PATH may resolve a different shim.

## OpenCode Environment Contract

Canonical keys:

- `HARNESS_OPENROUTER_API_KEY`
- `HARNESS_OPENROUTER_BASE_URL`
- `HARNESS_OPENROUTER_MODEL`
- `OPENCODE_NATIVE_CLI` (optional absolute path override)

Compatibility keys still supported:

- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`

OpenCode wrapper precedence (highest to lowest):

1. Process env `HARNESS_*`
2. Process env `OPENROUTER_*`
3. Local `cli-harness/.env` `HARNESS_*`
4. Local `cli-harness/.env` `OPENROUTER_*`

`OPENAI_API_KEY` is set only in the spawned child process for native OpenCode compatibility.

## Troubleshooting

Check deterministic resolution:

```powershell
python C:\Users\keith\dev\cli-harness\opencodeopen.py --dry-run
```

If PATH points to wrapper recursion, set native CLI explicitly:

```powershell
$env:OPENCODE_NATIVE_CLI="C:\Users\keith\AppData\Roaming\npm\opencode.cmd"
python C:\Users\keith\dev\cli-harness\opencodeopen.py --dry-run
```

If `HARNESS_OPENCODE_WRAPPER_ACTIVE` recursion guard appears, your selected `opencode` executable is a shim that points back to this wrapper.
