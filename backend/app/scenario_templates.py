from __future__ import annotations

from typing import Mapping

from backend.domain.scenario_models import (
    ScenarioDifficulty,
    ScenarioLayoutType,
    ScenarioParams,
    ScenarioTemplateDefinition,
)

KEY_GATE_SCENARIO_TEMPLATE_ID = "key_gate_scenario"
DEFAULT_SCENARIO_THEME = "watchtower"
DEFAULT_SCENARIO_AREA_COUNT = 6
DEFAULT_SCENARIO_LAYOUT_TYPE: ScenarioLayoutType = "branch"
DEFAULT_SCENARIO_DIFFICULTY: ScenarioDifficulty = "easy"

_KEY_GATE_SCENARIO_TEMPLATE = ScenarioTemplateDefinition(
    template_id=KEY_GATE_SCENARIO_TEMPLATE_ID,
    template_version="v0",
    description=(
        "A small playable scenario with one hint source, one clue source, "
        "one required key item, one gated move, and one enter-target success rule."
    ),
    default_theme=DEFAULT_SCENARIO_THEME,
    default_area_count=DEFAULT_SCENARIO_AREA_COUNT,
    min_area_count=4,
    max_area_count=8,
    default_layout_type=DEFAULT_SCENARIO_LAYOUT_TYPE,
    default_difficulty=DEFAULT_SCENARIO_DIFFICULTY,
    allowed_layout_types=("linear", "branch"),
    allowed_difficulties=("easy", "standard"),
    required_roles=(
        "start_area",
        "hint_source",
        "clue_area",
        "clue_source",
        "granted_item",
        "gate_area",
        "gate_entity",
        "required_item",
        "target_area",
    ),
    has_hint_source=True,
)

_SCENARIO_TEMPLATES = {
    KEY_GATE_SCENARIO_TEMPLATE_ID: _KEY_GATE_SCENARIO_TEMPLATE,
}


def list_scenario_templates() -> list[ScenarioTemplateDefinition]:
    return [_copy_template(template) for template in _SCENARIO_TEMPLATES.values()]


def get_scenario_template(template_id: str) -> ScenarioTemplateDefinition:
    normalized_template_id = _normalize_template_id(template_id)
    template = _SCENARIO_TEMPLATES.get(normalized_template_id)
    if template is None:
        raise ValueError(f"unsupported scenario_template: {template_id}")
    return _copy_template(template)


def normalize_scenario_params(
    raw: Mapping[str, object] | None = None,
) -> ScenarioParams:
    payload = raw or {}
    raw_template_id = payload.get("scenario_template")
    normalized_template_id = (
        KEY_GATE_SCENARIO_TEMPLATE_ID
        if raw_template_id is None
        else _normalize_template_id(raw_template_id)
    )
    template = get_scenario_template(normalized_template_id)

    return ScenarioParams(
        scenario_template=template.template_id,
        theme=_normalize_theme(payload.get("theme"), default=template.default_theme),
        area_count=_normalize_area_count(
            payload.get("area_count"),
            default=template.default_area_count,
            min_value=template.min_area_count,
            max_value=template.max_area_count,
        ),
        layout_type=_normalize_layout_type(
            payload.get("layout_type"),
            default=template.default_layout_type,
            allowed=template.allowed_layout_types,
        ),
        difficulty=_normalize_difficulty(
            payload.get("difficulty"),
            default=template.default_difficulty,
            allowed=template.allowed_difficulties,
        ),
    )


def _copy_template(template: ScenarioTemplateDefinition) -> ScenarioTemplateDefinition:
    if hasattr(template, "model_copy"):
        return template.model_copy(deep=True)
    return template.copy(deep=True)


def _normalize_template_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("scenario_template must be a string")
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("scenario_template must be non-empty")
    return normalized


def _normalize_theme(value: object, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError("theme must be a string")
    normalized = " ".join(value.strip().lower().split())
    return normalized or default


def _normalize_area_count(
    value: object,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("area_count must be an integer")
    if value < min_value or value > max_value:
        raise ValueError(f"area_count must be between {min_value} and {max_value}")
    return value


def _normalize_layout_type(
    value: object,
    *,
    default: ScenarioLayoutType,
    allowed: tuple[ScenarioLayoutType, ...],
) -> ScenarioLayoutType:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError("layout_type must be a string")
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized == "branched":
        normalized = "branch"
    if normalized not in allowed:
        raise ValueError(f"layout_type must be one of: {', '.join(allowed)}")
    return normalized  # type: ignore[return-value]


def _normalize_difficulty(
    value: object,
    *,
    default: ScenarioDifficulty,
    allowed: tuple[ScenarioDifficulty, ...],
) -> ScenarioDifficulty:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError("difficulty must be a string")
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized not in allowed:
        raise ValueError(f"difficulty must be one of: {', '.join(allowed)}")
    return normalized  # type: ignore[return-value]
