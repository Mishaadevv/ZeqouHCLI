# Changelog

## Repository preparation

- Added GitHub Actions CI across Python 3.10–3.13 and package build validation.
- Added tagged-release workflow for publishing wheel and source distribution artifacts.
- Added contribution/security guides, package project URLs, developer extras, and distribution manifest.
- Updated README with GitHub installation, usage, context limitations, and development commands.


## 0.5.0

- Fixed `/new` and `/resume` session UX: clear the visible terminal view, print a distinct session ID and preview resumed history.
- Fixed `/resume` without an ID so it selects the most recent *other* session instead of reloading the current empty session.
- Added automatic model-metadata discovery from provider `/models` records when adding/switching providers and models.
- Calculates the usable context cap from reported model and upstream-provider limits, choosing the more restrictive value when both exist.
- Added `/model-info`, `/effort`, and `/vision`; exposed thinking-effort and vision modes in `/settings` and `/set`.
- Selects a provider-declared effort value in `auto` mode where available; reports when effort values are only common suggestions rather than explicitly declared.
- Implemented local image-reference conversion into actual OpenAI-style `image_url` data payloads for vision-capable models. Stored session history keeps local paths rather than base64 image data.
- Added approximate image-token budgeting and displays the last API request's exact input token count when the provider reports usage.
- Added regression tests for session separation/resume, capability metadata, effort selection and image payload serialization.

## 0.4.0

- Added `/settings` with an interactive menu for tool visibility, tool results, thinking output, current file/page activity, token/context summaries, agent tool calling, web access, and web search result count.
- Added provider reasoning-stream display when the API exposes a separate reasoning field.
- Added public-web tools `web_search` and `web_open` with URL safety checks.
- Added current-file/current-page activity and token/context summary visibility.

## 0.3.1

- Fixed prompt_toolkit prompt rendering on Python 3.12/3.13.
- Added a regression test for prompt rendering.
