# CLI Harness Wrappers

This repository is the source of truth for local harness launcher wrappers.

## OpenCode Deterministic Launch

During repair and validation, run OpenCode from this repo only:

```powershell
C:\Users\keith\dev\cli-harness\opencode.cmd run "Reply with OK" --dangerously-skip-permissions --pure
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
