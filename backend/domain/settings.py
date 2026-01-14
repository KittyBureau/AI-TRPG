from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field

from backend.domain.models import SettingsSnapshot


class SettingDefinition(BaseModel):
    key: str
    type: str
    default: Any
    scope: str
    validation: Dict[str, Any] = Field(default_factory=dict)
    ui_hint: str
    effect_tags: List[str] = Field(default_factory=list)


_DEFINITIONS: List[SettingDefinition] = [
    SettingDefinition(
        key="context.full_context_enabled",
        type="bool",
        default=True,
        scope="campaign",
        validation={},
        ui_hint="toggle",
        effect_tags=["context"],
    ),
    SettingDefinition(
        key="context.compress_enabled",
        type="bool",
        default=False,
        scope="campaign",
        validation={},
        ui_hint="toggle",
        effect_tags=["context"],
    ),
    SettingDefinition(
        key="rules.hp_zero_ends_game",
        type="bool",
        default=True,
        scope="campaign",
        validation={},
        ui_hint="toggle",
        effect_tags=["rules"],
    ),
    SettingDefinition(
        key="rollback.max_checkpoints",
        type="int",
        default=0,
        scope="campaign",
        validation={"min": 0, "max": 10},
        ui_hint="number",
        effect_tags=["rollback"],
    ),
    SettingDefinition(
        key="dialog.auto_type_enabled",
        type="bool",
        default=True,
        scope="campaign",
        validation={},
        ui_hint="toggle",
        effect_tags=["dialog"],
    ),
]


def get_definitions() -> List[SettingDefinition]:
    return list(_DEFINITIONS)


def get_definition_map() -> Dict[str, SettingDefinition]:
    return {definition.key: definition for definition in _DEFINITIONS}


def apply_settings_patch(
    snapshot: SettingsSnapshot, patch: Dict[str, Any]
) -> Tuple[SettingsSnapshot, List[str]]:
    definition_map = get_definition_map()
    snapshot_data = _model_to_dict(snapshot)
    candidate_data = deepcopy(snapshot_data)
    changed_keys: List[str] = []

    for key, value in patch.items():
        if key not in definition_map:
            raise ValueError(f"Unknown setting key: {key}")
        definition = definition_map[key]
        _validate_value(definition, value)
        _set_by_path(candidate_data, key, value)

    for definition in definition_map.values():
        _validate_value(definition, _get_by_path(candidate_data, definition.key))

    candidate = SettingsSnapshot(**candidate_data)
    _validate_snapshot(candidate)

    for key in patch.keys():
        if _get_by_path(snapshot_data, key) != _get_by_path(candidate_data, key):
            changed_keys.append(key)

    return candidate, changed_keys


def _model_to_dict(model: object) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    raise TypeError("Unsupported model type")


def _validate_value(definition: SettingDefinition, value: Any) -> None:
    expected_type = definition.type
    if expected_type == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"Setting {definition.key} must be a bool")
    elif expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Setting {definition.key} must be an int")
        min_value = definition.validation.get("min")
        max_value = definition.validation.get("max")
        if min_value is not None and value < min_value:
            raise ValueError(f"Setting {definition.key} must be >= {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Setting {definition.key} must be <= {max_value}")
    else:
        raise ValueError(f"Unsupported setting type: {expected_type}")


def _validate_snapshot(snapshot: SettingsSnapshot) -> None:
    if snapshot.context.full_context_enabled and snapshot.context.compress_enabled:
        raise ValueError(
            "context.full_context_enabled and context.compress_enabled cannot both be true"
        )


def _set_by_path(data: Dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    cursor = data
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value


def _get_by_path(data: Dict[str, Any], key: str) -> Any:
    parts = key.split(".")
    cursor: Any = data
    for part in parts:
        cursor = cursor[part]
    return cursor
