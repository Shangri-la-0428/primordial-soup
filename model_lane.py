from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable


VALID_TRANSPORTS = ("anthropic_messages", "openai_chat_completions")
DEFAULT_MODEL_PROFILE_ID = "kimi"
PROFILE_REGISTRY_SCHEMA_VERSION = 1
PROFILE_REGISTRY_PATH = Path(__file__).resolve().parent / "config" / "model_profiles.json"
PROFILE_REGISTRY_LOCAL_PATH = Path(__file__).resolve().parent / "config" / "model_profiles.local.json"


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    provider: str
    transport: str
    api_url: str
    model: str
    api_key_env: str | None = None
    api_key: str | None = None
    max_tokens: int = 40
    max_workers: int = 20


@dataclass(frozen=True)
class LLMConfig:
    profile_id: str
    provider: str
    transport: str
    api_url: str
    api_key: str
    model: str
    max_tokens: int = 40
    max_workers: int = 20

    def metadata(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "transport": self.transport,
            "api_url": self.api_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "max_workers": self.max_workers,
        }


def _coerce_message_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "".join(parts)
    return None


@dataclass(frozen=True)
class TransportAdapter:
    name: str
    request_builder: Callable[[LLMConfig, str], tuple[bytes, dict[str, str]]]
    response_parser: Callable[[dict[str, Any]], str | None]

    def build_request(self, config: LLMConfig, prompt: str) -> urllib.request.Request:
        body, headers = self.request_builder(config, prompt)
        return urllib.request.Request(config.api_url, data=body, headers=headers, method="POST")

    def parse_response(self, payload: dict[str, Any]) -> str | None:
        return self.response_parser(payload)


def _build_anthropic_request(config: LLMConfig, prompt: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": config.max_tokens,
        }
    ).encode()
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    return body, headers


def _parse_anthropic_response(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        return None
    return _coerce_message_text(content)


def _build_openai_request(config: LLMConfig, prompt: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": config.max_tokens,
        }
    ).encode()
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    return body, headers


def _parse_openai_response(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    return _coerce_message_text(message.get("content"))


TRANSPORT_ADAPTERS = {
    "anthropic_messages": TransportAdapter(
        name="anthropic_messages",
        request_builder=_build_anthropic_request,
        response_parser=_parse_anthropic_response,
    ),
    "openai_chat_completions": TransportAdapter(
        name="openai_chat_completions",
        request_builder=_build_openai_request,
        response_parser=_parse_openai_response,
    ),
}


FALLBACK_MODEL_PROFILES = {
    "kimi": ModelProfile(
        profile_id="kimi",
        provider="kimi",
        transport="anthropic_messages",
        api_url="https://api.lkeap.cloud.tencent.com/plan/anthropic/v1/messages",
        model="kimi-k2.5",
        api_key_env="KIMI_API_KEY",
        max_tokens=40,
        max_workers=40,
    ),
    "anthropic-compatible": ModelProfile(
        profile_id="anthropic-compatible",
        provider="anthropic",
        transport="anthropic_messages",
        api_url="https://api.anthropic.com/v1/messages",
        model="claude-3-7-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        max_tokens=40,
        max_workers=40,
    ),
    "openai-compatible": ModelProfile(
        profile_id="openai-compatible",
        provider="openai",
        transport="openai_chat_completions",
        api_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4.1-mini",
        api_key_env="OPENAI_API_KEY",
        max_tokens=40,
        max_workers=40,
    ),
}


def load_profile_registry(
    path: Path | None = None,
    overlay_path: Path | None = None,
) -> tuple[str, dict[str, ModelProfile]]:
    registry_path = path or PROFILE_REGISTRY_PATH
    base_default_profile_id = DEFAULT_MODEL_PROFILE_ID
    base_profiles = dict(FALLBACK_MODEL_PROFILES)

    if registry_path.exists():
        base_default_profile_id, base_profiles = _parse_registry_payload(
            registry_path,
            allow_merge=False,
            existing_profiles={},
            existing_default_profile_id=DEFAULT_MODEL_PROFILE_ID,
        )

    resolved_overlay_path = overlay_path
    if resolved_overlay_path is None and path is None and PROFILE_REGISTRY_LOCAL_PATH.exists():
        resolved_overlay_path = PROFILE_REGISTRY_LOCAL_PATH

    if resolved_overlay_path and resolved_overlay_path.exists():
        base_default_profile_id, base_profiles = _parse_registry_payload(
            resolved_overlay_path,
            allow_merge=True,
            existing_profiles=base_profiles,
            existing_default_profile_id=base_default_profile_id,
        )

    return base_default_profile_id, base_profiles


def _parse_registry_payload(
    registry_path: Path,
    *,
    allow_merge: bool,
    existing_profiles: dict[str, ModelProfile],
    existing_default_profile_id: str,
) -> tuple[str, dict[str, ModelProfile]]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    schema_version = payload.get("schema_version")
    if schema_version != PROFILE_REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported model profile schema version {schema_version}; expected {PROFILE_REGISTRY_SCHEMA_VERSION}"
        )
    profiles_payload = payload.get("profiles")
    if not isinstance(profiles_payload, list) or not profiles_payload:
        raise ValueError("model profile registry must contain a non-empty 'profiles' list")

    profiles = dict(existing_profiles)
    seen_in_file: set[str] = set()
    for raw in profiles_payload:
        profile = ModelProfile(
            profile_id=raw["profile_id"],
            provider=raw["provider"],
            transport=raw["transport"],
            api_url=raw["api_url"],
            model=raw["model"],
            api_key_env=raw.get("api_key_env"),
            api_key=raw.get("api_key"),
            max_tokens=raw.get("max_tokens", 40),
            max_workers=raw.get("max_workers", 20),
        )
        get_transport_adapter(profile.transport)
        if profile.profile_id in seen_in_file:
            raise ValueError(f"duplicate model profile '{profile.profile_id}' in {registry_path}")
        if not allow_merge and profile.profile_id in profiles:
            raise ValueError(f"duplicate model profile '{profile.profile_id}' in {registry_path}")
        profiles[profile.profile_id] = profile
        seen_in_file.add(profile.profile_id)

    default_profile_id = payload.get("default_profile_id", existing_default_profile_id)
    if default_profile_id not in profiles:
        raise ValueError(
            f"default model profile '{default_profile_id}' is not defined in {registry_path}"
        )
    return default_profile_id, profiles


def list_model_profiles(
    *,
    registry_path: Path | None = None,
    overlay_path: Path | None = None,
) -> list[dict[str, Any]]:
    default_profile_id, profiles = load_profile_registry(
        path=registry_path,
        overlay_path=overlay_path,
    )
    rendered: list[dict[str, Any]] = []
    for profile_id in sorted(profiles):
        profile = profiles[profile_id]
        rendered.append(
            {
                "profile_id": profile.profile_id,
                "provider": profile.provider,
                "transport": profile.transport,
                "api_url": profile.api_url,
                "model": profile.model,
                "api_key_env": profile.api_key_env,
                "default": profile.profile_id == default_profile_id,
            }
        )
    return rendered


def _launchctl_getenv(name: str) -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["launchctl", "getenv", name],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    value = result.stdout.strip()
    return value or None


def _resolve_named_secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return _launchctl_getenv(name)


def check_model_profile(
    profile_id: str,
    *,
    registry_path: Path | None = None,
    overlay_path: Path | None = None,
) -> dict[str, Any]:
    profile = load_model_profile(
        profile_id,
        registry_path=registry_path,
        overlay_path=overlay_path,
    )
    env_name = profile.api_key_env
    process_env_present = bool(os.environ.get(env_name, "")) if env_name else False
    launchctl_env_present = bool(_launchctl_getenv(env_name)) if env_name else False
    ready = bool(profile.api_key) or process_env_present or launchctl_env_present
    resolved_source: str | None
    if profile.api_key:
        resolved_source = "profile"
    elif process_env_present:
        resolved_source = "process_env"
    elif launchctl_env_present:
        resolved_source = "launchctl_env"
    else:
        resolved_source = None
    return {
        "profile_id": profile.profile_id,
        "provider": profile.provider,
        "transport": profile.transport,
        "api_url": profile.api_url,
        "model": profile.model,
        "api_key_env": env_name,
        "process_env_present": process_env_present,
        "launchctl_env_present": launchctl_env_present,
        "resolved_source": resolved_source,
        "ready": ready,
    }


def get_transport_adapter(name: str) -> TransportAdapter:
    try:
        return TRANSPORT_ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown transport '{name}'; expected one of {', '.join(VALID_TRANSPORTS)}"
        ) from exc


def load_model_profile(
    profile_id: str | None,
    *,
    profiles: dict[str, ModelProfile] | None = None,
    registry_path: Path | None = None,
    overlay_path: Path | None = None,
) -> ModelProfile:
    if profiles is None:
        default_profile_id, profile_table = load_profile_registry(
            registry_path,
            overlay_path=overlay_path,
        )
    else:
        default_profile_id, profile_table = DEFAULT_MODEL_PROFILE_ID, profiles
    profile_key = profile_id or default_profile_id
    try:
        profile = profile_table[profile_key]
    except KeyError as exc:
        raise ValueError(
            f"unknown model profile '{profile_key}'; available profiles: {', '.join(sorted(profile_table))}"
        ) from exc
    get_transport_adapter(profile.transport)
    return profile


def _default_env_name_for_transport(transport: str) -> str | None:
    if transport == "anthropic_messages":
        return "ANTHROPIC_API_KEY"
    if transport == "openai_chat_completions":
        return "OPENAI_API_KEY"
    return None


def resolve_llm_config(
    *,
    profile_id: str | None = None,
    transport: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    max_workers: int | None = None,
    profiles: dict[str, ModelProfile] | None = None,
    registry_path: Path | None = None,
    overlay_path: Path | None = None,
) -> LLMConfig:
    profile = load_model_profile(
        profile_id,
        profiles=profiles,
        registry_path=registry_path,
        overlay_path=overlay_path,
    )

    overrides: dict[str, Any] = {}
    if transport is not None:
        get_transport_adapter(transport)
        overrides["transport"] = transport
    if api_url is not None:
        overrides["api_url"] = api_url
    if model is not None:
        overrides["model"] = model
    if max_tokens is not None:
        overrides["max_tokens"] = max_tokens
    if max_workers is not None:
        overrides["max_workers"] = max_workers
    if overrides:
        profile = replace(profile, **overrides)

    resolved_key = api_key
    if resolved_key is None:
        if profile.api_key:
            resolved_key = profile.api_key
        elif profile.api_key_env:
            resolved_key = _resolve_named_secret(profile.api_key_env)
        else:
            fallback_env_name = _default_env_name_for_transport(profile.transport)
            if fallback_env_name:
                resolved_key = _resolve_named_secret(fallback_env_name)

    if not resolved_key:
        env_hint = profile.api_key_env or _default_env_name_for_transport(profile.transport) or "an API key env var"
        raise ValueError(
            f"missing API key for profile '{profile.profile_id}'; provide --api-key or set {env_hint}"
        )

    return LLMConfig(
        profile_id=profile.profile_id,
        provider=profile.provider,
        transport=profile.transport,
        api_url=profile.api_url,
        api_key=resolved_key,
        model=profile.model,
        max_tokens=profile.max_tokens,
        max_workers=profile.max_workers,
    )
