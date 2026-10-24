from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from .config import endpoint_for, models_endpoint_for
from .sessions import estimate_messages_tokens, estimate_tokens


class APIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _normalize_usage(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt_tokens", raw.get("input_tokens"))
    completion = raw.get("completion_tokens", raw.get("output_tokens"))
    if prompt is None and completion is None:
        return None
    try:
        return {"input_tokens": int(prompt or 0), "output_tokens": int(completion or 0)}
    except (TypeError, ValueError):
        return None


class OpenAICompatibleClient:
    """Small OpenAI Chat Completions-compatible client with SSE streaming."""

    def __init__(self, provider: dict[str, Any], temperature: float | None = 0.2, max_output_tokens: int | None = None) -> None:
        self.provider = provider
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("ZEQOUHCLI_API_KEY") or str(self.provider.get("api_key", ""))
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        extra = self.provider.get("extra_headers", {})
        if isinstance(extra, dict):
            for name, value in extra.items():
                if isinstance(name, str) and isinstance(value, str) and name.lower() not in {"authorization", "content-type"}:
                    headers[name] = value
        return headers

    def _request_body(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        include_usage: bool,
        include_effort: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.provider.get("model", ""),
            "messages": messages,
            "stream": True,
        }
        if include_effort:
            effort = str(self.provider.get("thinking_effort", "auto") or "auto").lower()
            model_meta = self.provider.get("model_metadata")
            model_meta = model_meta if isinstance(model_meta, dict) and model_meta.get("model_id") == self.provider.get("model") else {}
            effort_supported = model_meta.get("reasoning_effort_supported")
            if effort == "auto":
                # Pick a value the registry actually listed when available. If it
                # only reports parameter support, use the common medium default.
                declared = model_meta.get("supported_reasoning_efforts")
                declared = [str(v).lower() for v in declared if isinstance(v, str)] if isinstance(declared, list) else []
                default_effort = model_meta.get("default_reasoning_effort")
                if default_effort and (not declared or str(default_effort).lower() in declared):
                    effort = str(default_effort).lower()
                elif effort_supported is True:
                    effort = "medium" if "medium" in declared or not declared else declared[0]
                else:
                    effort = ""
            if effort and effort != "auto" and effort_supported is not False:
                parameter = model_meta.get("reasoning_parameter", "reasoning_effort")
                if parameter == "reasoning":
                    body["reasoning"] = {"effort": effort}
                elif parameter != "unsupported":
                    body["reasoning_effort"] = effort
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.max_output_tokens:
            body["max_tokens"] = int(self.max_output_tokens)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if include_usage:
            body["stream_options"] = {"include_usage": True}
        return body

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        endpoint = endpoint_for(str(self.provider.get("base_url", "")))
        include_usage = True
        include_effort = True
        effort_fallback_warning = ""
        while True:
            body = self._request_body(messages, tools, include_usage, include_effort)
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    result = self._consume_sse(response, messages, on_text, on_thinking)
                    if effort_fallback_warning:
                        result["warnings"] = [effort_fallback_warning]
                    return result
            except urllib.error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")[:8000]
                if include_usage and exc.code in {400, 422} and ("stream_options" in response_body or "include_usage" in response_body):
                    include_usage = False
                    continue
                if include_effort and exc.code in {400, 422} and any(term in response_body.lower() for term in ("reasoning_effort", "reasoning effort", "unsupported parameter: reasoning", "unknown parameter 'reasoning'")):
                    include_effort = False
                    effort_fallback_warning = "Provider rejected the configured reasoning-effort parameter; retried using its default."
                    continue
                detail = response_body.strip() or str(exc.reason)
                raise APIError(f"API returned HTTP {exc.code}: {detail}", exc.code, response_body) from exc
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                raise APIError(f"Could not connect to API at {endpoint}: {reason}") from exc
            except TimeoutError as exc:
                raise APIError("Request timed out after 300 seconds") from exc

    def _consume_sse(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        on_text: Callable[[str], None] | None,
        on_thinking: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_deltas: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] | None = None
        any_event = False
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            payload_text = line[5:].strip()
            if payload_text == "[DONE]":
                break
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            any_event = True
            parsed_usage = _normalize_usage(payload.get("usage"))
            if parsed_usage is not None:
                usage = parsed_usage
            choices = payload.get("choices") or []
            if not choices:
                continue
            choice = choices[0] if isinstance(choices[0], dict) else {}
            delta = choice.get("delta") or {}
            # Some compatible providers stream reasoning in a dedicated field.
            # Display it only when the caller explicitly enables the thinking view.
            reasoning_chunk = next((delta.get(key) for key in ("reasoning_content", "reasoning", "analysis", "thinking") if isinstance(delta.get(key), str) and delta.get(key)), None)
            if isinstance(reasoning_chunk, str) and reasoning_chunk:
                thinking_parts.append(reasoning_chunk)
                if on_thinking:
                    on_thinking(reasoning_chunk)
            text_chunk = delta.get("content")
            if isinstance(text_chunk, str) and text_chunk:
                content_parts.append(text_chunk)
                if on_text:
                    on_text(text_chunk)
            for tool in delta.get("tool_calls") or []:
                if not isinstance(tool, dict):
                    continue
                try:
                    index = int(tool.get("index", 0))
                except (TypeError, ValueError):
                    index = 0
                item = tool_deltas.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if tool.get("id") and not item["id"]:
                    item["id"] = str(tool["id"])
                if tool.get("type"):
                    item["type"] = tool["type"]
                function = tool.get("function") or {}
                if function.get("name"):
                    item["function"]["name"] += str(function["name"])
                if function.get("arguments"):
                    item["function"]["arguments"] += str(function["arguments"])
        if not any_event:
            raise APIError("The API returned an empty stream. Check the base URL and model name.")
        calls = []
        for index in sorted(tool_deltas):
            call = tool_deltas[index]
            if not call["id"]:
                call["id"] = f"call_{index}"
            calls.append(call)
        content = "".join(content_parts)
        exact_usage = usage is not None
        if usage is None:
            usage = {
                "input_tokens": estimate_messages_tokens(messages),
                "output_tokens": estimate_tokens(content + json.dumps(calls, ensure_ascii=False)),
            }
        return {"content": content, "thinking": "".join(thinking_parts), "tool_calls": calls, "usage": usage, "exact_usage": exact_usage}

    def discover_remote_models(self) -> list[dict[str, Any]]:
        """Fetch full model records when an OpenAI-compatible provider exposes them."""
        endpoint = models_endpoint_for(str(self.provider.get("base_url", "")))
        request = urllib.request.Request(endpoint, headers={k: v for k, v in self._headers().items() if k != "Accept"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8", errors="replace"))
            items = body.get("data", []) if isinstance(body, dict) else []
            return [item for item in items if isinstance(item, dict) and item.get("id")]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            return []

    def list_remote_models(self) -> list[str]:
        return sorted({str(item.get("id")) for item in self.discover_remote_models() if item.get("id")})
