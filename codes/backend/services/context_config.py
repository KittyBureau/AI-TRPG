import json
from dataclasses import dataclass
from typing import List

from backend.secrets.manager import CONFIG_PATH

DEFAULT_CONTEXT_STRATEGY = "full_context"
DEFAULT_INJECTION_PRIORITY = ["character_sheet", "rules_text", "world_state"]
ALLOWED_INJECTION_KEYS = {"character_sheet", "rules_text", "world_state"}


class ContextConfigError(Exception):
    pass


@dataclass(frozen=True)
class ContextConfig:
    context_strategy: str
    injection_priority: List[str]
    character_sheet_path: str | None
    rules_text_path: str | None
    world_state_path: str | None
    log_tokens: bool
    persona_lock_enabled: bool


def _as_optional_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def load_context_config() -> ContextConfig:
    if not CONFIG_PATH.exists():
        raise ContextConfigError(f"Config file not found: {CONFIG_PATH}")
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContextConfigError("Config file is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ContextConfigError("Config file must be a JSON object.")

    strategy = payload.get("context_strategy", DEFAULT_CONTEXT_STRATEGY)
    if not isinstance(strategy, str) or not strategy:
        raise ContextConfigError("context_strategy must be a non-empty string.")

    priority = payload.get("injection_priority", DEFAULT_INJECTION_PRIORITY)
    if not isinstance(priority, list) or not all(isinstance(item, str) for item in priority):
        raise ContextConfigError("injection_priority must be a list of strings.")
    for item in priority:
        if item not in ALLOWED_INJECTION_KEYS:
            raise ContextConfigError(f"Unknown injection type: {item}")

    log_tokens = payload.get("log_tokens", True)
    if not isinstance(log_tokens, bool):
        raise ContextConfigError("log_tokens must be a boolean.")

    persona_lock_enabled = payload.get("persona_lock_enabled", True)
    if not isinstance(persona_lock_enabled, bool):
        raise ContextConfigError("persona_lock_enabled must be a boolean.")

    return ContextConfig(
        context_strategy=strategy,
        injection_priority=priority,
        character_sheet_path=_as_optional_path(payload.get("character_sheet_path")),
        rules_text_path=_as_optional_path(payload.get("rules_text_path")),
        world_state_path=_as_optional_path(payload.get("world_state_path")),
        log_tokens=log_tokens,
        persona_lock_enabled=persona_lock_enabled,
    )
