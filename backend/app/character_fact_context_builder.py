from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from backend.domain.models import Campaign
from backend.infra.file_repo import FileRepo

if TYPE_CHECKING:
    from backend.app.character_fact_generation import CharacterFactGenerationRequest

_ALLOWED_PARTY_CONTEXT_KEYS = {
    "character_id",
    "name",
    "role",
    "summary",
    "tags",
    "attributes",
    "background",
    "appearance",
    "personality_tags",
    "meta",
}


@dataclass
class CharacterFactPromptBuildResult:
    system_prompt: str
    user_payload: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


class CharacterFactContextBuilder:
    def build(
        self,
        repo: FileRepo,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> CharacterFactPromptBuildResult:
        request_trimmed, trim_warnings = _trim_party_context(request.party_context)
        campaign = repo.get_campaign(request.campaign_id)
        authoritative = _build_authoritative_party_context(repo, campaign)
        merged, merge_warnings = _merge_party_context(
            request_trimmed,
            authoritative,
        )
        warnings = [*trim_warnings, *merge_warnings]

        user_payload = {
            "language": request.language,
            "tone_style": list(request.tone_style),
            "tone_vocab_only": request.tone_vocab_only,
            "allowed_tones": list(request.allowed_tones),
            "constraints": dict(request.constraints),
            "count": count,
            "max_count": request.max_count,
            "id_policy": request.id_policy,
            "authoritative_rule": "storage_authoritative_request_advisory",
            "party_context": merged,
        }

        system_prompt = (
            "You are generating CharacterFact draft candidates for AI-TRPG. "
            "Output MUST be valid JSON object with key 'items' whose value is an array of CharacterFact-like draft objects. "
            "Do not output markdown. "
            "Only generate static profile fields and never output runtime fields position/hp/character_state. "
            "Respect constraints.allowed_roles, language/tone inputs, and count. "
            "For id_policy=system set character_id='__AUTO_ID__'. "
            "When party_context conflicts with storage-authoritative context, prioritize storage values. "
            f"Context: {json.dumps(user_payload, ensure_ascii=False)}"
        )

        return CharacterFactPromptBuildResult(
            system_prompt=system_prompt,
            user_payload=user_payload,
            warnings=warnings,
        )


def _build_authoritative_party_context(repo: FileRepo, campaign: Campaign) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for actor_id in campaign.selected.party_character_ids:
        if not isinstance(actor_id, str) or not actor_id.strip():
            continue
        payload = repo.load_character_fact_draft(campaign.id, actor_id)
        if payload is None:
            payload = repo.load_character_fact_from_batches(campaign.id, actor_id)

        actor = campaign.actors.get(actor_id)
        actor_meta = actor.meta if actor and isinstance(actor.meta, dict) else {}
        profile = actor_meta.get("profile") if isinstance(actor_meta.get("profile"), dict) else {}

        base: Dict[str, Any] = {}
        if isinstance(payload, dict):
            base.update(payload)
        if isinstance(profile, dict):
            for key, value in profile.items():
                base.setdefault(key, value)
        for key in (
            "name",
            "role",
            "summary",
            "tags",
            "attributes",
            "background",
            "appearance",
            "personality_tags",
            "meta",
        ):
            if key in base:
                continue
            if key in actor_meta:
                base[key] = actor_meta.get(key)

        base["character_id"] = actor_id
        normalized, _ = _normalize_party_context_item(base, item_index=-1)
        if normalized:
            items.append(normalized)
    return items


def _merge_party_context(
    request_trimmed: List[Dict[str, Any]],
    authoritative: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    authoritative_by_id = {
        item.get("character_id"): item
        for item in authoritative
        if isinstance(item.get("character_id"), str)
    }

    merged: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in request_trimmed:
        character_id = item.get("character_id")
        if isinstance(character_id, str) and character_id in authoritative_by_id:
            authoritative_item = authoritative_by_id[character_id]
            if _item_conflicts(item, authoritative_item):
                warnings.append(
                    f"party_context[{character_id}] conflicts with storage-authoritative data; request values ignored for overlapping keys."
                )
            merged.append(dict(authoritative_item))
            seen_ids.add(character_id)
            continue

        merged.append(dict(item))
        if isinstance(character_id, str):
            seen_ids.add(character_id)

    for item in authoritative:
        character_id = item.get("character_id")
        if isinstance(character_id, str) and character_id in seen_ids:
            continue
        merged.append(dict(item))

    return merged, warnings


def _item_conflicts(request_item: Dict[str, Any], authoritative_item: Dict[str, Any]) -> bool:
    for key, value in request_item.items():
        if key == "character_id" or key not in authoritative_item:
            continue
        if authoritative_item.get(key) != value:
            return True
    return False


def _trim_party_context(value: object) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not isinstance(value, list):
        return [], []

    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            warnings.append(f"party_context[{index}] ignored: item must be object.")
            continue
        normalized, item_warnings = _normalize_party_context_item(item, item_index=index)
        warnings.extend(item_warnings)
        if normalized:
            items.append(normalized)

    return items, warnings


def _normalize_party_context_item(
    item: Dict[str, Any],
    *,
    item_index: int,
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    normalized: Dict[str, Any] = {}
    prefix = "authoritative" if item_index < 0 else f"party_context[{item_index}]"

    for key in item.keys():
        if key not in _ALLOWED_PARTY_CONTEXT_KEYS:
            warnings.append(f"{prefix}.{key} dropped: key not allowed.")

    character_id, trimmed = _trim_string(item.get("character_id"), 80)
    if trimmed:
        warnings.append(f"{prefix}.character_id trimmed to 80 chars.")
    if character_id:
        normalized["character_id"] = character_id

    name, trimmed = _trim_string(item.get("name"), 80)
    if trimmed:
        warnings.append(f"{prefix}.name trimmed to 80 chars.")
    if name:
        normalized["name"] = name

    role, trimmed = _trim_string(item.get("role"), 40)
    if trimmed:
        warnings.append(f"{prefix}.role trimmed to 40 chars.")
    if role:
        normalized["role"] = role

    summary, trimmed = _trim_string(item.get("summary"), 240)
    if trimmed:
        warnings.append(f"{prefix}.summary trimmed to 240 chars.")
    if summary:
        normalized["summary"] = summary

    background, trimmed = _trim_string(item.get("background"), 400)
    if trimmed:
        warnings.append(f"{prefix}.background trimmed to 400 chars.")
    if background:
        normalized["background"] = background

    appearance, trimmed = _trim_string(item.get("appearance"), 240)
    if trimmed:
        warnings.append(f"{prefix}.appearance trimmed to 240 chars.")
    if appearance:
        normalized["appearance"] = appearance

    tags, trimmed = _trim_string_list(item.get("tags"), max_items=8, max_length=24)
    if trimmed:
        warnings.append(
            f"{prefix}.tags normalized to max 8 unique items with max length 24."
        )
    if tags:
        normalized["tags"] = tags

    personality_tags, trimmed = _trim_string_list(
        item.get("personality_tags"),
        max_items=8,
        max_length=24,
    )
    if trimmed:
        warnings.append(
            f"{prefix}.personality_tags normalized to max 8 unique items with max length 24."
        )
    if personality_tags:
        normalized["personality_tags"] = personality_tags

    attributes = _trim_attributes(item.get("attributes"))
    if attributes:
        normalized["attributes"] = attributes

    meta, trimmed = _trim_meta(item.get("meta"))
    if trimmed:
        warnings.append(f"{prefix}.meta normalized by whitelist/length limits.")
    if meta:
        normalized["meta"] = meta

    return normalized, warnings


def _trim_string(value: object, max_length: int) -> Tuple[str, bool]:
    if not isinstance(value, str):
        return "", False
    cleaned = value.strip()
    if not cleaned:
        return "", False
    if len(cleaned) > max_length:
        return cleaned[:max_length], True
    return cleaned, False


def _trim_string_list(
    value: object,
    *,
    max_items: int,
    max_length: int,
) -> Tuple[List[str], bool]:
    if not isinstance(value, list):
        return [], False
    result: List[str] = []
    seen: set[str] = set()
    changed = False
    for item in value:
        if not isinstance(item, str):
            changed = True
            continue
        cleaned = item.strip()
        if not cleaned:
            changed = True
            continue
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
            changed = True
        if cleaned in seen:
            changed = True
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= max_items:
            if len(value) > len(result):
                changed = True
            break
    return result, changed


def _trim_attributes(value: object) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(item, (str, int, float, bool)):
            normalized[key] = item
    return normalized


def _trim_meta(value: object) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(value, dict):
        return {}, False

    hooks, hooks_trimmed = _trim_string_list(value.get("hooks"), max_items=5, max_length=80)
    language, language_trimmed = _trim_string(value.get("language"), 24)
    source, source_trimmed = _trim_string(value.get("source"), 24)

    normalized: Dict[str, Any] = {}
    if hooks:
        normalized["hooks"] = hooks
    if language:
        normalized["language"] = language
    if source:
        normalized["source"] = source
    allowed = {"hooks", "language", "source"}
    dropped_unknown = any(key not in allowed for key in value.keys())
    changed = hooks_trimmed or language_trimmed or source_trimmed or dropped_unknown
    return normalized, changed
