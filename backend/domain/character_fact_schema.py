from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping

FORBIDDEN_RUNTIME_FIELDS = {"position", "hp", "character_state"}
REQUIRED_FIELDS = {
    "character_id",
    "name",
    "role",
    "tags",
    "attributes",
    "background",
    "appearance",
    "personality_tags",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"meta"}
ALLOWED_META_FIELDS = {"hooks", "language", "source"}
CHARACTER_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


class CharacterFactSchemaError(ValueError):
    """Raised when a payload violates character_fact.v1 schema rules."""


def is_valid_character_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    trimmed = value.strip()
    if len(trimmed) < 3 or len(trimmed) > 64:
        return False
    return CHARACTER_ID_PATTERN.fullmatch(trimmed) is not None


def validate_character_fact(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CharacterFactSchemaError("CharacterFact must be an object.")

    keys = set(payload.keys())
    forbidden = keys & FORBIDDEN_RUNTIME_FIELDS
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise CharacterFactSchemaError(f"Forbidden runtime field(s): {names}")

    missing = REQUIRED_FIELDS - keys
    if missing:
        names = ", ".join(sorted(missing))
        raise CharacterFactSchemaError(f"Missing required field(s): {names}")

    unknown = keys - ALLOWED_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise CharacterFactSchemaError(f"Unknown field(s): {names}")

    character_id = _read_trimmed_string(payload.get("character_id"), "character_id")
    if not is_valid_character_id(character_id):
        raise CharacterFactSchemaError("character_id format is invalid.")

    name = _read_trimmed_string(payload.get("name"), "name")
    if len(name) > 80:
        raise CharacterFactSchemaError("name exceeds max length 80.")

    role = _read_trimmed_string(payload.get("role"), "role")
    if len(role) > 40:
        raise CharacterFactSchemaError("role exceeds max length 40.")

    tags = _validate_string_list(
        payload.get("tags"),
        key="tags",
        max_items=8,
        max_length=24,
    )
    personality_tags = _validate_string_list(
        payload.get("personality_tags"),
        key="personality_tags",
        max_items=8,
        max_length=24,
    )

    attributes = payload.get("attributes")
    if not isinstance(attributes, Mapping):
        raise CharacterFactSchemaError("attributes must be an object.")
    normalized_attributes: Dict[str, Any] = {}
    for key, value in attributes.items():
        if not isinstance(key, str):
            raise CharacterFactSchemaError("attributes keys must be strings.")
        if isinstance(value, (str, int, float, bool)):
            normalized_attributes[key] = value
            continue
        raise CharacterFactSchemaError(
            f"attributes.{key} must be string/number/boolean."
        )

    background = payload.get("background")
    if not isinstance(background, str):
        raise CharacterFactSchemaError("background must be a string.")
    if len(background) > 400:
        raise CharacterFactSchemaError("background exceeds max length 400.")

    appearance = payload.get("appearance")
    if not isinstance(appearance, str):
        raise CharacterFactSchemaError("appearance must be a string.")
    if len(appearance) > 240:
        raise CharacterFactSchemaError("appearance exceeds max length 240.")

    meta = payload.get("meta")
    normalized_meta: Dict[str, Any] = {}
    if meta is not None:
        if not isinstance(meta, Mapping):
            raise CharacterFactSchemaError("meta must be an object.")
        unknown_meta = set(meta.keys()) - ALLOWED_META_FIELDS
        if unknown_meta:
            names = ", ".join(sorted(unknown_meta))
            raise CharacterFactSchemaError(f"Unknown meta field(s): {names}")
        if "hooks" in meta:
            normalized_meta["hooks"] = _validate_string_list(
                meta.get("hooks"),
                key="meta.hooks",
                max_items=5,
                max_length=80,
            )
        if "language" in meta:
            language = meta.get("language")
            if not isinstance(language, str):
                raise CharacterFactSchemaError("meta.language must be a string.")
            normalized_meta["language"] = language
        if "source" in meta:
            source = meta.get("source")
            if not isinstance(source, str):
                raise CharacterFactSchemaError("meta.source must be a string.")
            normalized_meta["source"] = source

    validated: Dict[str, Any] = {
        "character_id": character_id,
        "name": name,
        "role": role,
        "tags": tags,
        "attributes": normalized_attributes,
        "background": background,
        "appearance": appearance,
        "personality_tags": personality_tags,
    }
    if normalized_meta:
        validated["meta"] = normalized_meta
    return validated


def _validate_string_list(
    value: object,
    *,
    key: str,
    max_items: int,
    max_length: int,
) -> list[str]:
    if not isinstance(value, list):
        raise CharacterFactSchemaError(f"{key} must be an array.")
    if len(value) > max_items:
        raise CharacterFactSchemaError(f"{key} exceeds max items {max_items}.")
    if not _all_unique(value):
        raise CharacterFactSchemaError(f"{key} must not contain duplicates.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise CharacterFactSchemaError(f"{key} values must be strings.")
        if len(item) < 1:
            raise CharacterFactSchemaError(f"{key} values must not be empty.")
        if len(item) > max_length:
            raise CharacterFactSchemaError(
                f"{key} values exceed max length {max_length}."
            )
        result.append(item)
    return result


def _read_trimmed_string(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise CharacterFactSchemaError(f"{key} must be a string.")
    trimmed = value.strip()
    if not trimmed:
        raise CharacterFactSchemaError(f"{key} must not be empty.")
    return trimmed


def _all_unique(values: Iterable[object]) -> bool:
    seen = set()
    for value in values:
        if value in seen:
            return False
        seen.add(value)
    return True
