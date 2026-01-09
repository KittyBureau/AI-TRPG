from dataclasses import dataclass
from typing import List

from backend.services.context_config import ALLOWED_GUARDS, ContextConfig


class DialogRoutingError(Exception):
    pass


@dataclass(frozen=True)
class DialogRouteDecision:
    dialog_type: str
    variant: str
    context_profile: str
    response_style: str
    guards: List[str]


def _normalize_token(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise DialogRoutingError(f"{field} must be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise DialogRoutingError(f"{field} must be non-empty.")
    return cleaned.lower()


def _normalize_guards(guards: List[str] | None, default_guards: List[str]) -> List[str]:
    if guards is None:
        return list(default_guards)
    if not isinstance(guards, list) or not all(isinstance(item, str) for item in guards):
        raise DialogRoutingError("guards must be a list of strings.")
    cleaned = []
    seen = set()
    for guard in guards:
        token = guard.strip()
        if not token:
            continue
        if token not in ALLOWED_GUARDS:
            raise DialogRoutingError(f"Unknown guard: {token}")
        if token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned


def resolve_dialog_route(
    config: ContextConfig,
    dialog_type: str | None = None,
    variant: str | None = None,
    context_profile: str | None = None,
    response_style: str | None = None,
    guards: List[str] | None = None,
) -> DialogRouteDecision:
    defaults = config.dialog_route_default
    default_type = _normalize_token(defaults.dialog_type, "dialog_type")
    default_variant = _normalize_token(defaults.variant, "variant")
    default_style = _normalize_token(defaults.response_style, "response_style")
    resolved_type = _normalize_token(dialog_type, "dialog_type") if dialog_type else default_type
    resolved_variant = _normalize_token(variant, "variant") if variant else default_variant
    resolved_style = _normalize_token(response_style, "response_style") if response_style else default_style
    resolved_guards = _normalize_guards(guards, defaults.guards)

    profile_id = None
    if context_profile:
        if not isinstance(context_profile, str) or not context_profile.strip():
            raise DialogRoutingError("context_profile must be a non-empty string.")
        profile_id = context_profile.strip()
    else:
        route_key = f"{resolved_type}.{resolved_variant}"
        profile_id = config.dialog_routes.get(route_key)
        if not profile_id:
            fallback_key = f"{default_type}.{default_variant}"
            profile_id = config.dialog_routes.get(fallback_key)
        if not profile_id:
            raise DialogRoutingError(f"Route not found for {resolved_type}.{resolved_variant}.")

    if profile_id not in config.context_profiles:
        raise DialogRoutingError(f"Unknown context_profile: {profile_id}")

    return DialogRouteDecision(
        dialog_type=resolved_type,
        variant=resolved_variant,
        context_profile=profile_id,
        response_style=resolved_style,
        guards=resolved_guards,
    )
