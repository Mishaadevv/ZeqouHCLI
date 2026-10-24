from __future__ import annotations

import re
from typing import Any

EFFORT_LEVELS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
COMMON_EFFORT_LEVELS = ["low", "medium", "high"]
_CONTEXT_KEYS = (
    "context_length",
    "context_window",
    "max_context_tokens",
    "max_input_tokens",
    "input_token_limit",
    "max_sequence_length",
    "max_model_len",
    "max_position_embeddings",
    "model_max_length",
)
_IMAGE_MODEL_HINTS = (
    "gemini", "claude-3", "claude-4", "gpt-4o", "gpt-4.1", "gpt-5", "gpt-6",
    "qwen-vl", "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "llava", "pixtral",
    "internvl", "minicpm-v", "glm-4v", "gemma-3", "gemma3", "gemma-4", "gemma4",
    "llama-4", "molmo", "vision", "multimodal",
)
_REASONING_MODEL_HINTS = ("gpt-5", "gpt-6", "o1", "o3", "o4", "deepseek-r1", "qwq", "reasoner", "thinking")


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if 256 <= result <= 100_000_000 else None


def _smallest_positive(objects: list[dict[str, Any]], keys: tuple[str, ...]) -> int | None:
    """Return the smallest reported cap; smaller input limits must not be ignored."""
    values: list[int] = []
    for obj in objects:
        for key in keys:
            value = _positive_int(obj.get(key))
            if value is not None:
                values.append(value)
    return min(values) if values else None


def extract_model_metadata(item: dict[str, Any], model_id: str | None = None) -> dict[str, Any]:
    """Normalize model limits/capabilities from an OpenAI-compatible /models record.

    Reported limits are kept distinct from name-based guesses. For router-style
    registries, usable context is capped by both the model window and the selected
    upstream provider's context limit when both are available.
    """
    model_id = str(model_id or item.get("id") or "")
    architecture = item.get("architecture") if isinstance(item.get("architecture"), dict) else {}
    top_provider = item.get("top_provider") if isinstance(item.get("top_provider"), dict) else {}
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    limits = item.get("limits") if isinstance(item.get("limits"), dict) else {}

    model_context = _smallest_positive([item, architecture, limits, metadata], _CONTEXT_KEYS)
    upstream_context = _smallest_positive([top_provider], _CONTEXT_KEYS)
    known_contexts = [v for v in (model_context, upstream_context) if v is not None]
    context_window = min(known_contexts) if known_contexts else None
    if model_context is not None and upstream_context is not None and model_context != upstream_context:
        context_source = "provider + model metadata (most restrictive limit)"
    elif model_context is not None:
        context_source = "provider model metadata"
    elif upstream_context is not None:
        context_source = "upstream provider metadata"
    else:
        context_source = "unknown; using configured fallback"

    modalities_raw: Any = architecture.get("input_modalities")
    if not isinstance(modalities_raw, list):
        modalities_raw = item.get("input_modalities", item.get("modalities"))
    modalities = [str(v).lower() for v in modalities_raw if isinstance(v, (str, int))] if isinstance(modalities_raw, list) else []
    if not modalities and isinstance(architecture.get("modality"), str):
        modality = architecture["modality"].lower()
        modalities = [part.strip() for part in re.split(r"->|,", modality.split("->", 1)[0]) if part.strip()]

    params_raw = item.get("supported_parameters", item.get("supported_params"))
    supported_parameters = [str(v).lower() for v in params_raw] if isinstance(params_raw, list) else []
    declared_efforts = item.get("reasoning_efforts", item.get("supported_reasoning_efforts"))
    if not isinstance(declared_efforts, list):
        declared_efforts = metadata.get("reasoning_efforts") if isinstance(metadata.get("reasoning_efforts"), list) else None
    if isinstance(declared_efforts, list):
        supported_efforts = [str(v).lower() for v in declared_efforts if str(v).lower() in EFFORT_LEVELS]
        effort_source = "provider model metadata"
    else:
        supported_efforts = []
        effort_source = "not reported"

    if "reasoning_effort" in supported_parameters:
        effort_supported: bool | None = True
        reasoning_parameter = "reasoning_effort"
    elif "reasoning" in supported_parameters:
        effort_supported = True
        reasoning_parameter = "reasoning"
    elif isinstance(declared_efforts, list) and declared_efforts:
        effort_supported = True
        reasoning_parameter = "reasoning_effort"
    elif supported_parameters:
        effort_supported = False
        reasoning_parameter = "unsupported"
    else:
        model_hint = model_id.lower()
        effort_supported = True if any(hint in model_hint for hint in _REASONING_MODEL_HINTS) else None
        reasoning_parameter = "reasoning_effort" if effort_supported else "unknown"
        if effort_supported:
            effort_source = "model-name inference; API compatibility not confirmed"

    # A registry often reports that reasoning_effort is accepted but omits the
    # legal values. Offer conservative common values without calling them exact.
    if effort_supported is True and not supported_efforts:
        supported_efforts = list(COMMON_EFFORT_LEVELS)
        if effort_source == "not reported":
            effort_source = "common values; provider did not enumerate levels"

    if modalities:
        vision_capability: bool | None = any(v in {"image", "images", "vision"} for v in modalities)
        image_source = "provider metadata"
    else:
        normalized_id = model_id.lower()
        if any(hint in normalized_id for hint in _IMAGE_MODEL_HINTS):
            vision_capability = True
            image_source = "model-name inference; verify provider support"
        else:
            vision_capability = None
            image_source = "unknown"

    return {
        "model_id": model_id,
        "context_window": context_window,
        "context_source": context_source,
        "model_context_window": model_context,
        "provider_context_window": upstream_context,
        "input_modalities": modalities,
        "supports_images": vision_capability,
        "image_source": image_source,
        "supported_parameters": supported_parameters,
        "reasoning_effort_supported": effort_supported,
        "reasoning_parameter": reasoning_parameter,
        "supported_reasoning_efforts": supported_efforts,
        "reasoning_efforts_source": effort_source,
        "metadata_available": bool(item),
    }


def effective_context_window(config: dict[str, Any], provider: dict[str, Any] | None) -> tuple[int, str]:
    """Pick the best known input-window cap and label how reliable it is."""
    if isinstance(config.get("context_window_override"), int) and not isinstance(config.get("context_window_override"), bool):
        override = _positive_int(config["context_window_override"])
        if override is not None:
            return override, "manual override"
    if provider:
        model_meta = provider.get("model_metadata")
        if isinstance(model_meta, dict) and model_meta.get("model_id") == provider.get("model"):
            detected = _positive_int(model_meta.get("context_window"))
            if detected is not None:
                return detected, str(model_meta.get("context_source") or "provider model metadata")
        provider_value = _positive_int(provider.get("context_window"))
        if provider_value is not None:
            return provider_value, "provider configuration"
    default = _positive_int(config.get("context_window")) or 128_000
    return default, "fallback (actual model/provider limit not reported)"


def supports_images(provider: dict[str, Any] | None, vision_mode: str = "auto") -> bool:
    mode = str(vision_mode or "auto").lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    if not provider:
        return False
    meta = provider.get("model_metadata")
    if isinstance(meta, dict) and meta.get("model_id") == provider.get("model"):
        detected = meta.get("supports_images")
        if isinstance(detected, bool):
            return detected
    return False


def effort_options(provider: dict[str, Any] | None) -> list[str]:
    if not provider:
        return []
    meta = provider.get("model_metadata")
    if not isinstance(meta, dict) or meta.get("model_id") != provider.get("model"):
        return []
    values = meta.get("supported_reasoning_efforts")
    return [str(value) for value in values if str(value) in EFFORT_LEVELS] if isinstance(values, list) else []
