# Zeqou[H]CLI — Zeqou Harness CLI

A compact terminal AI coding agent that can inspect and edit a project, run approved commands, research public web pages, and send project images to compatible vision models. Built for OpenAI-compatible Chat Completions providers.

> **Release:** 0.5.0 · **Python:** 3.10+ · **License:** MIT

## Features

- Interactive terminal chat with visible tool activity and file diffs.
- Project-scoped saved conversations, `/new`, `/resume`, and `/compact`.
- Configurable provider URL, API key, model, and reasoning effort.
- Model/provider metadata discovery for context limits and capabilities where available.
- File read/search/edit tools and shell commands with approval prompts by default.
- Public web search/page reading and optional image inspection for vision-capable models.
- Cross-platform Python package and `zeqouhcli` console command.

## Install

Python 3.10 or newer is required.

### Windows — one-command installer

Open PowerShell and paste this command. It downloads the public source from GitHub, installs ZeqouHCLI and its dependencies, and adds the Python Scripts directory to your user `PATH` automatically. No administrator rights or Git installation are required.

```powershell
irm https://raw.githubusercontent.com/Mishaadevv/ZeqouHCLI/main/install.ps1 | iex
```

After installation, open any project directory in PowerShell and run:

```powershell
zeqouhcli
```

### Install from a source checkout

**Windows**

```powershell
.\install.bat
```

**Linux/macOS**

```sh
python3 -m pip install --user .
```

If your shell has not refreshed `PATH` yet, use `py -3 -m zeqouhcli` as a fallback.

## Run inside a project

Open a terminal in the directory the agent should work in, then run `zeqouhcli` or `py -3 -m zeqouhcli`. The current working directory is the project root for file tools.

Use `/connect` to configure the provider base URL, model ID, and API key. Then ask the agent to inspect, edit, or test the current project. Review proposed diffs and keep command/file approvals enabled unless you know why you need a different policy.

## Useful commands

| Command | Purpose |
| --- | --- |
| `/connect` | Configure provider, base URL, model, and key |
| `/models` | List models and discover metadata where exposed |
| `/model-info` | Inspect context and model capabilities |
| `/effort auto\|none\|minimal\|low\|medium\|high\|xhigh\|max` | Select reasoning effort where supported |
| `/vision auto\|on\|off` | Configure vision support |
| `/settings` | Configure tool, thinking, activity, and usage display |
| `/new [title]` | Start a separate saved session |
| `/resume [id]` | Resume another session |
| `/sessions` | List sessions for this project |
| `/context` | Show context estimate and last reported usage |
| `/compact` | Summarize history to reduce future input tokens |
| `/init` | Create `AGENTS.md` project instructions |
| `/permissions ask\|auto` | Set tool approval policy |
| `/help` | Show all available commands |

## Context and provider compatibility

When a provider reports model metadata through its `/models` endpoint, Zeqou records context limits and capabilities. If both a model-specific and provider-level limit are available, it uses the more restrictive reported limit. When metadata is unavailable, it shows a fallback or inferred value instead of claiming the limit is verified.

Context percentage is an estimate before requests because tokenizers and hidden provider prompt formatting vary. If the API reports prompt-token usage, Zeqou displays that exact reported count for the completed request. Reasoning, tool calls, usage reporting, and vision support depend on the selected provider/model API implementation.

## Images and web access

For vision-capable models, the agent can inspect supported image files in the project and send image payloads to the configured provider. Image bytes leave the local machine when sent for analysis. The agent also provides local image transforms. Public web tools can search and read HTTP(S) pages; local/loopback addresses are blocked and web content is treated as untrusted input.

## Publish from a local checkout (maintainers)

The repository's `publish.ps1` helper initializes Git, creates the first commit, and pushes to the public repository. If [GitHub CLI](https://cli.github.com/) is installed and authenticated (`gh auth login`), it can create `Mishaadevv/ZeqouHCLI` as a public repository automatically. Otherwise, create an **empty** public repository named `ZeqouHCLI` at https://github.com/new first (do not initialize it with a README or license), then run `./publish.ps1` in PowerShell.

## Development and tests

```powershell
py -3 -m pip install -e ".[dev]"
py -3 -m pytest -q
py -3 -m build
py -3 -m twine check dist/*
```

CI tests Python 3.10–3.13 and checks built distributions. Tag a release with `v0.5.0` (or the next version) to build artifacts and create a GitHub Release automatically.

## Security

Do not commit API keys, `.env`, local `config.json`, or chat-session files. Review diffs and approve file writes/shell commands intentionally. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
