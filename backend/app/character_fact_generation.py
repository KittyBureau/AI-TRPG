from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from backend.infra.file_repo import FileRepo

FORBIDDEN_RUNTIME_FIELDS = {"position", "hp", "character_state"}


@dataclass(frozen=True)
class CharacterFactGenerationConfig:
    generation_mode: str = "batch"
    id_policy: str = "system"
    output_language_mode: str = "single"
    default_language: str = "zh-CN"
    tone_vocab_only_flag: bool = True
    role_policy: str = "allowlist"
    tag_conflict_policy: str = "allow"
    attribute_strictness: str = "open"
    hook_generation_mode: str = "typed"
    count_default: int = 3
    count_max: int = 20
    validation_pipeline: str = "draft+normalize"
    persistence_style: str = "batch+individual"
    conflict_types: Sequence[str] = (
        "name",
        "tags",
        "role",
        "personality_tags",
    )
    prompt_management: str = "structured"
    meta_extension_policy: str = "predefined-only"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation_mode": self.generation_mode,
            "id_policy": self.id_policy,
            "output_language_mode": self.output_language_mode,
            "default_language": self.default_language,
            "tone_vocab_only_flag": self.tone_vocab_only_flag,
            "role_policy": self.role_policy,
            "tag_conflict_policy": self.tag_conflict_policy,
            "attribute_strictness": self.attribute_strictness,
            "hook_generation_mode": self.hook_generation_mode,
            "count_policy": {
                "default": self.count_default,
                "max": self.count_max,
            },
            "validation_pipeline": self.validation_pipeline,
            "persistence_style": self.persistence_style,
            "conflict_types": list(self.conflict_types),
            "prompt_management": self.prompt_management,
            "meta_extension_policy": self.meta_extension_policy,
        }


@dataclass
class CharacterFactGenerationRequest:
    campaign_id: str
    request_id: str
    language: str = "zh-CN"
    tone_style: List[str] = field(default_factory=list)
    tone_vocab_only: bool = True
    allowed_tones: List[str] = field(default_factory=list)
    party_context: List[Dict[str, Any]] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    count: int = 3
    max_count: int = 20
    id_policy: str = "system"

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "request_id": self.request_id,
            "language": self.language,
            "tone_style": list(self.tone_style),
            "tone_vocab_only": self.tone_vocab_only,
            "allowed_tones": list(self.allowed_tones),
            "party_context": list(self.party_context),
            "constraints": dict(self.constraints),
            "count": self.count,
            "max_count": self.max_count,
            "id_policy": self.id_policy,
        }


@dataclass
class CharacterFactBatchWriteResult:
    batch_path: str
    individual_paths: List[str]
    items: List[Dict[str, Any]]


class CharacterFactGenerationService:
    def __init__(
        self,
        repo: FileRepo,
        config: CharacterFactGenerationConfig | None = None,
    ) -> None:
        self.repo = repo
        self.config = config or CharacterFactGenerationConfig()

    def persist_generated_batch(
        self,
        request: CharacterFactGenerationRequest,
        drafts: Sequence[Mapping[str, Any]],
    ) -> CharacterFactBatchWriteResult:
        normalized_items = self._normalize_batch(request, drafts)
        batch_payload = {
            "schema_version": "character_fact.v1",
            "request_id": request.request_id,
            "campaign_id": request.campaign_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_snapshot": self.config.to_dict(),
            "request_snapshot": request.to_snapshot(),
            "items": normalized_items,
        }
        batch_path = self.repo.save_character_fact_batch(
            request.campaign_id,
            request.request_id,
            batch_payload,
        )

        individual_paths: List[str] = []
        for index, item in enumerate(normalized_items, start=1):
            character_id = item["character_id"]
            if character_id == "__AUTO_ID__":
                file_id = f"__AUTO_ID___{index:03d}"
            else:
                file_id = character_id
            path = self.repo.save_character_fact_draft(
                request.campaign_id,
                file_id,
                item,
            )
            individual_paths.append(str(path))

        return CharacterFactBatchWriteResult(
            batch_path=str(batch_path),
            individual_paths=individual_paths,
            items=normalized_items,
        )

    def _normalize_batch(
        self,
        request: CharacterFactGenerationRequest,
        drafts: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        limit = max(0, min(request.count, request.max_count, self.config.count_max))
        selected: List[Mapping[str, Any]] = list(drafts[:limit])
        while len(selected) < limit:
            selected.append({})

        normalized: List[Dict[str, Any]] = []
        used_ids: Dict[str, int] = {}
        for index, draft in enumerate(selected, start=1):
            item = self._normalize_item(request, draft, index)
            character_id = item["character_id"]
            if character_id != "__AUTO_ID__":
                item["character_id"] = self._dedupe_id(character_id, used_ids)
            normalized.append(item)
        return normalized

    def _normalize_item(
        self,
        request: CharacterFactGenerationRequest,
        draft: Mapping[str, Any],
        index: int,
    ) -> Dict[str, Any]:
        allowed_roles = self._read_str_list(request.constraints.get("allowed_roles"))
        name_default = f"Character {index}"
        role_default = allowed_roles[0] if allowed_roles else "unknown"

        raw_id = draft.get("character_id")
        if request.id_policy == "system":
            character_id = "__AUTO_ID__"
        elif isinstance(raw_id, str) and raw_id.strip():
            character_id = raw_id.strip()
        else:
            character_id = f"generated_{index:03d}"

        role = self._read_string(draft.get("role"), role_default, 40)
        if allowed_roles and role not in allowed_roles:
            role = role_default

        normalized: Dict[str, Any] = {
            "character_id": character_id,
            "name": self._read_string(draft.get("name"), name_default, 80),
            "role": role,
            "tags": self._normalize_string_list(draft.get("tags"), 8, 24),
            "attributes": self._normalize_attributes(draft.get("attributes")),
            "background": self._read_string(draft.get("background"), "", 400),
            "appearance": self._read_string(draft.get("appearance"), "", 240),
            "personality_tags": self._normalize_string_list(
                draft.get("personality_tags"), 8, 24
            ),
        }

        for field in FORBIDDEN_RUNTIME_FIELDS:
            normalized.pop(field, None)

        meta = self._normalize_meta(draft.get("meta"), request.language)
        if meta:
            normalized["meta"] = meta
        return normalized

    def _normalize_attributes(self, value: object) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if isinstance(item, (str, int, float, bool)):
                normalized[key] = item
        return normalized

    def _normalize_meta(self, value: object, language: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            value = {}
        hooks = self._normalize_string_list(value.get("hooks"), 5, 80)
        source = self._read_string(value.get("source"), "llm", 24)
        lang = self._read_string(value.get("language"), language or "zh-CN", 24)
        meta: Dict[str, Any] = {}
        if hooks:
            meta["hooks"] = hooks
        if lang:
            meta["language"] = lang
        if source:
            meta["source"] = source
        return meta

    def _normalize_string_list(
        self,
        value: object,
        max_items: int,
        max_length: int,
    ) -> List[str]:
        if not isinstance(value, list):
            return []
        result: List[str] = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if not cleaned:
                continue
            if len(cleaned) > max_length:
                cleaned = cleaned[:max_length]
            if cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
            if len(result) >= max_items:
                break
        return result

    def _read_string(self, value: object, default: str, max_length: int) -> str:
        if not isinstance(value, str):
            return default
        cleaned = value.strip()
        if not cleaned:
            return default
        if len(cleaned) > max_length:
            return cleaned[:max_length]
        return cleaned

    def _read_str_list(self, value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]

    def _dedupe_id(self, value: str, used_ids: Dict[str, int]) -> str:
        index = used_ids.get(value, 0)
        used_ids[value] = index + 1
        if index == 0:
            return value
        return f"{value}_{index + 1}"
