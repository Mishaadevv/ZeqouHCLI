# Contributing

Thanks for helping improve Zeqou[H]CLI.

## Development setup

Python 3.10 or newer is required.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

On Linux/macOS, activate with `source .venv/bin/activate`.

## Before opening a pull request

- Add or update tests for behavior changes.
- Run `python -m pytest -q`.
- Do not commit API keys, `.env` files, local configuration, or session data.
- Describe provider-specific limitations and manual test steps.

## Scope

Keep the terminal interface compact, preserve project-directory boundaries, and ask before risky file writes or shell commands unless the user explicitly changes the permission setting.
