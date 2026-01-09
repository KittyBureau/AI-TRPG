import json
from dataclasses import dataclass
from typing import Dict, List

from backend.secrets.manager import CONFIG_PATH

DEFAULT_CONTEXT_STRATEGY = "full_context"
DEFAULT_INJECTION_PRIORITY = ["character_sheet", "rules_text", "world_state"]
ALLOWED_CONTEXT_BLOCKS = {
    "character_sheet",
    "character_state",
    "rules_text",
    "world_state",
    "lore",
    "session_summary",
    "key_facts",
    "recent_turns",
}
ALLOWED_CONTEXT_STRATEGIES = {"full_context", "compact_context", "auto"}
ALLOWED_GUARDS = {"persona_lock", "role_confusion_guard"}

DEFAULT_DIALOG_ROUTE = {
    "dialog_type": "narrative",
    "variant": "scene_general",
    "response_style": "default",
    "guards": ["persona_lock", "role_confusion_guard"],
}
DEFAULT_DIALOG_ROUTES = {
    "narrative.scene_pure": "nar_scene_pure",
    "narrative.scene_general": "nar_scene_general",
    "action_intent.light": "act_light",
    "rules_query.explain": "rules_explain",
}
DEFAULT_CONTEXT_PROFILES: Dict[str, Dict[str, object]] = {
    "nar_scene_pure": {
        "include_blocks": ["lore", "session_summary", "recent_turns"],
        "exclude_blocks": ["character_sheet", "rules_text", "character_state"],
        "limits": {"lore": 1200, "session_summary": 1500, "recent_turns": 1200},
        "recent_turns_n": 4,
        "strategy": "full_context",
    },
    "nar_scene_general": {
        "include_blocks": ["character_state", "world_state", "session_summary", "recent_turns"],
        "exclude_blocks": ["character_sheet", "rules_text"],
        "limits": {
            "character_state": 800,
            "world_state": 800,
            "session_summary": 1500,
            "recent_turns": 1200,
        },
        "recent_turns_n": 4,
        "strategy": "full_context",
    },
    "act_light": {
        "include_blocks": ["character_state", "world_state", "recent_turns"],
        "exclude_blocks": ["character_sheet", "rules_text"],
        "limits": {"character_state": 900, "world_state": 900, "recent_turns": 1200},
        "recent_turns_n": 3,
        "strategy": "full_context",
    },
    "rules_explain": {
        "include_blocks": ["rules_text"],
        "exclude_blocks": [
            "character_sheet",
            "character_state",
            "world_state",
            "lore",
            "key_facts",
            "session_summary",
            "recent_turns",
        ],
        "limits": {"rules_text": 2000},
        "recent_turns_n": 0,
        "strategy": "compact_context",
    },
}


class ContextConfigError(Exception):
    pass


@dataclass(frozen=True)
class ContextProfile:
    profile_id: str
    include_blocks: List[str]
    exclude_blocks: List[str]
    limits: Dict[str, int]
    recent_turns_n: int
    strategy: str


@dataclass(frozen=True)
class DialogRouteDefaults:
    dialog_type: str
    variant: str
    response_style: str
    guards: List[str]


@dataclass(frozen=True)
class ContextConfig:
    context_strategy: str
    injection_priority: List[str]
    character_sheet_path: str | None
    character_state_path: str | None
    rules_text_path: str | None
    world_state_path: str | None
    lore_path: str | None
    log_tokens: bool
    persona_lock_enabled: bool
    dialog_route_default: DialogRouteDefaults
    dialog_routes: Dict[str, str]
    context_profiles: Dict[str, ContextProfile]


def _as_optional_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_string_list(value: object, field: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContextConfigError(f"{field} must be a list of strings.")
    cleaned = []
    for item in value:
        token = item.strip()
        if token:
            cleaned.append(token)
    return cleaned


def _parse_limits(value: object) -> Dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContextConfigError("limits must be a JSON object.")
    limits: Dict[str, int] = {}
    for key, raw in value.items():
        if key not in ALLOWED_CONTEXT_BLOCKS:
            raise ContextConfigError(f"Unknown limits block: {key}")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ContextConfigError(f"Limit for {key} must be an integer.")
        if raw <= 0:
            raise ContextConfigError(f"Limit for {key} must be > 0.")
        limits[key] = raw
    return limits


def _parse_profile(profile_id: str, payload: object) -> ContextProfile:
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ContextConfigError("Profile id must be a non-empty string.")
    if not isinstance(payload, dict):
        raise ContextConfigError(f"Profile '{profile_id}' must be a JSON object.")

    include_blocks = _require_string_list(payload.get("include_blocks", []), "include_blocks")
    exclude_blocks = _require_string_list(payload.get("exclude_blocks", []), "exclude_blocks")
    for item in include_blocks + exclude_blocks:
        if item not in ALLOWED_CONTEXT_BLOCKS:
            raise ContextConfigError(f"Unknown context block: {item}")

    limits = _parse_limits(payload.get("limits"))
    recent_turns_n = payload.get("recent_turns_n", 0)
    if isinstance(recent_turns_n, bool) or not isinstance(recent_turns_n, int):
        raise ContextConfigError("recent_turns_n must be an integer.")
    if recent_turns_n < 0:
        raise ContextConfigError("recent_turns_n must be >= 0.")

    strategy = payload.get("strategy", DEFAULT_CONTEXT_STRATEGY)
    if not isinstance(strategy, str) or not strategy:
        raise ContextConfigError("strategy must be a non-empty string.")
    if strategy not in ALLOWED_CONTEXT_STRATEGIES:
        raise ContextConfigError(f"Unsupported context strategy: {strategy}")

    return ContextProfile(
        profile_id=profile_id.strip(),
        include_blocks=include_blocks,
        exclude_blocks=exclude_blocks,
        limits=limits,
        recent_turns_n=recent_turns_n,
        strategy=strategy,
    )


def _build_profiles_from_dict(payload: Dict[str, object]) -> Dict[str, ContextProfile]:
    profiles: Dict[str, ContextProfile] = {}
    for profile_id, profile_payload in payload.items():
        profiles[profile_id] = _parse_profile(profile_id, profile_payload)
    return profiles


def _parse_profiles(value: object) -> Dict[str, ContextProfile]:
    if value is None:
        return _build_profiles_from_dict(DEFAULT_CONTEXT_PROFILES)
    if not isinstance(value, dict):
        raise ContextConfigError("context_profiles must be a JSON object.")
    return _build_profiles_from_dict(value)


def _parse_dialog_routes(value: object) -> Dict[str, str]:
    routes = dict(DEFAULT_DIALOG_ROUTES)
    if value is None:
        return routes
    if not isinstance(value, dict):
        raise ContextConfigError("dialog_routes must be a JSON object.")
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ContextConfigError("dialog_routes keys must be non-empty strings.")
        if not isinstance(raw, str) or not raw.strip():
            raise ContextConfigError("dialog_routes values must be non-empty strings.")
        routes[key.strip()] = raw.strip()
    return routes


def _parse_dialog_route_default(value: object) -> DialogRouteDefaults:
    if value is None:
        payload = DEFAULT_DIALOG_ROUTE
    else:
        if not isinstance(value, dict):
            raise ContextConfigError("dialog_route_default must be a JSON object.")
        payload = dict(DEFAULT_DIALOG_ROUTE)
        for key in ("dialog_type", "variant", "response_style"):
            if key in value:
                if not isinstance(value[key], str) or not value[key].strip():
                    raise ContextConfigError(f"dialog_route_default.{key} must be a string.")
                payload[key] = value[key].strip()
        if "guards" in value:
            guards = _require_string_list(value["guards"], "dialog_route_default.guards")
            for guard in guards:
                if guard not in ALLOWED_GUARDS:
                    raise ContextConfigError(f"Unknown guard: {guard}")
            payload["guards"] = guards

    return DialogRouteDefaults(
        dialog_type=str(payload["dialog_type"]),
        variant=str(payload["variant"]),
        response_style=str(payload["response_style"]),
        guards=list(payload["guards"]),
    )


def _validate_routes_profiles(routes: Dict[str, str], profiles: Dict[str, ContextProfile]) -> None:
    missing = sorted({profile_id for profile_id in routes.values() if profile_id not in profiles})
    if missing:
        raise ContextConfigError(f"dialog_routes reference unknown profiles: {', '.join(missing)}")


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
        if item not in ALLOWED_CONTEXT_BLOCKS:
            raise ContextConfigError(f"Unknown injection type: {item}")

    log_tokens = payload.get("log_tokens", True)
    if not isinstance(log_tokens, bool):
        raise ContextConfigError("log_tokens must be a boolean.")

    persona_lock_enabled = payload.get("persona_lock_enabled", True)
    if not isinstance(persona_lock_enabled, bool):
        raise ContextConfigError("persona_lock_enabled must be a boolean.")

    dialog_route_default = _parse_dialog_route_default(payload.get("dialog_route_default"))
    dialog_routes = _parse_dialog_routes(payload.get("dialog_routes"))
    context_profiles = _parse_profiles(payload.get("context_profiles"))
    _validate_routes_profiles(dialog_routes, context_profiles)

    return ContextConfig(
        context_strategy=strategy,
        injection_priority=priority,
        character_sheet_path=_as_optional_path(payload.get("character_sheet_path")),
        character_state_path=_as_optional_path(payload.get("character_state_path")),
        rules_text_path=_as_optional_path(payload.get("rules_text_path")),
        world_state_path=_as_optional_path(payload.get("world_state_path")),
        lore_path=_as_optional_path(payload.get("lore_path")),
        log_tokens=log_tokens,
        persona_lock_enabled=persona_lock_enabled,
        dialog_route_default=dialog_route_default,
        dialog_routes=dialog_routes,
        context_profiles=context_profiles,
    )
