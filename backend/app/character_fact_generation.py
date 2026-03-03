from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence
from uuid import uuid4

from backend.app.character_fact_context_builder import CharacterFactContextBuilder
from backend.app.character_fact_llm_adapter import (
    CharacterFactLLMAdapter,
    CharacterFactLLMResult,
)
from backend.domain.character_fact_schema import (
    CharacterFactSchemaError,
    is_valid_character_id,
    validate_character_fact,
)
from backend.infra.file_repo import FileRepo

FORBIDDEN_RUNTIME_FIELDS = {"position", "hp", "character_state"}
CHARACTER_FACT_SCHEMA_ID = "character_fact.v1"
CHARACTER_FACT_SCHEMA_VERSION = "1"


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


class CharacterFactRequestError(ValueError):
    pass


class CharacterFactConflictError(RuntimeError):
    pass


class CharacterFactValidationError(ValueError):
    pass


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
    draft_mode: str = "deterministic"
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> Dict[str, Any]:
        snapshot = dict(self.extra_params)
        snapshot.update(
            {
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
                "draft_mode": self.draft_mode,
            }
        )
        return snapshot


@dataclass
class CharacterFactBatchWriteResult:
    campaign_id: str
    request_id: str
    utc_ts: str
    batch_path: str
    individual_paths: List[str]
    items: List[Dict[str, Any]]
    count_requested: int
    count_generated: int
    warnings: List[str] = field(default_factory=list)


@dataclass
class DraftGenerationResult:
    drafts: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)


class DraftGenerator(Protocol):
    def generate(
        self,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> DraftGenerationResult:
        ...


class DeterministicDraftGenerator:
    def __init__(self, service: "CharacterFactGenerationService") -> None:
        self.service = service

    def generate(
        self,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> DraftGenerationResult:
        return DraftGenerationResult(
            drafts=self.service._run_draft_phase(request, count),
            warnings=[],
        )


class LLMDraftGenerator:
    def __init__(
        self,
        repo: FileRepo,
        context_builder: CharacterFactContextBuilder,
        adapter: CharacterFactLLMAdapter,
    ) -> None:
        self.repo = repo
        self.context_builder = context_builder
        self.adapter = adapter

    def generate(
        self,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> DraftGenerationResult:
        build_result = self.context_builder.build(self.repo, request, count)
        llm_result: CharacterFactLLMResult = self.adapter.generate_drafts(
            system_prompt=build_result.system_prompt,
            user_payload=build_result.user_payload,
        )
        return DraftGenerationResult(
            drafts=llm_result.drafts,
            warnings=[*build_result.warnings, *llm_result.warnings],
        )


class CharacterFactGenerationService:
    def __init__(
        self,
        repo: FileRepo,
        config: CharacterFactGenerationConfig | None = None,
        *,
        context_builder: Optional[CharacterFactContextBuilder] = None,
        llm_adapter: Optional[CharacterFactLLMAdapter] = None,
    ) -> None:
        self.repo = repo
        self.config = config or CharacterFactGenerationConfig()
        self.context_builder = context_builder or CharacterFactContextBuilder()
        self.llm_adapter = llm_adapter

    def persist_generated_batch(
        self,
        request: CharacterFactGenerationRequest,
        drafts: Sequence[Mapping[str, Any]],
        *,
        count_override: int | None = None,
        warnings: Sequence[str] | None = None,
    ) -> CharacterFactBatchWriteResult:
        self._validate_request(request)
        existing = self.repo.find_character_fact_batch_path(
            request.campaign_id,
            request.request_id,
        )
        if existing is not None:
            raise CharacterFactConflictError(
                f"request_id already exists: {request.request_id}"
            )

        target_count, count_warnings = self._resolve_count(request)
        if count_override is not None:
            target_count = max(0, count_override)
            count_warnings = []
        all_warnings = list(count_warnings)
        if warnings:
            all_warnings.extend([message for message in warnings if isinstance(message, str)])

        normalized_items = self._run_normalize_phase(
            request,
            drafts,
            target_count,
        )
        normalized_items = self._allocate_character_ids(
            request.campaign_id,
            normalized_items,
        )
        validated_items = self._validate_items(normalized_items)
        utc_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        batch_payload = {
            "schema_id": CHARACTER_FACT_SCHEMA_ID,
            "schema_version": CHARACTER_FACT_SCHEMA_VERSION,
            "campaign_id": request.campaign_id,
            "request_id": request.request_id,
            "utc_ts": utc_ts,
            "params": request.to_snapshot(),
            "items": validated_items,
        }
        try:
            batch_path = self.repo.save_character_fact_batch(
                request.campaign_id,
                request.request_id,
                batch_payload,
                utc_ts=utc_ts,
            )
        except FileExistsError as exc:
            raise CharacterFactConflictError(
                f"request_id already exists: {request.request_id}"
            ) from exc

        individual_paths: List[str] = []
        for item in validated_items:
            character_id = item["character_id"]
            path = self.repo.save_character_fact_draft(
                request.campaign_id,
                character_id,
                item,
            )
            individual_paths.append(self.repo.to_storage_relative_path(path))

        return CharacterFactBatchWriteResult(
            campaign_id=request.campaign_id,
            request_id=request.request_id,
            utc_ts=utc_ts,
            batch_path=self.repo.to_storage_relative_path(batch_path),
            individual_paths=individual_paths,
            items=validated_items,
            count_requested=request.count,
            count_generated=len(validated_items),
            warnings=all_warnings,
        )

    def generate_and_persist(
        self,
        request: CharacterFactGenerationRequest,
    ) -> CharacterFactBatchWriteResult:
        self._validate_request(request)
        count, warnings = self._resolve_count(request)
        draft_result = self._generate_drafts(request, count)
        warnings = [*warnings, *draft_result.warnings]
        return self.persist_generated_batch(
            request,
            draft_result.drafts,
            count_override=count,
            warnings=warnings,
        )

    def make_request_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"req_{timestamp}_{uuid4().hex[:6]}"

    def _validate_request(self, request: CharacterFactGenerationRequest) -> None:
        if not isinstance(request.request_id, str) or not request.request_id.strip():
            raise CharacterFactRequestError("request_id must be a non-empty string.")
        if request.count <= 0:
            raise CharacterFactRequestError("count must be > 0.")
        if request.max_count <= 0:
            raise CharacterFactRequestError("max_count must be > 0.")
        if request.id_policy not in {"system", "model"}:
            raise CharacterFactRequestError("id_policy must be 'system' or 'model'.")
        if request.draft_mode not in {"deterministic", "llm"}:
            raise CharacterFactRequestError(
                "draft_mode must be 'deterministic' or 'llm'."
            )

        allowed_roles = self._read_str_list(request.constraints.get("allowed_roles"))
        if not allowed_roles:
            raise CharacterFactRequestError("constraints.allowed_roles must not be empty.")
        if request.tone_vocab_only and not self._read_str_list(request.allowed_tones):
            raise CharacterFactRequestError(
                "allowed_tones is required when tone_vocab_only=true."
            )

    def _resolve_count(self, request: CharacterFactGenerationRequest) -> tuple[int, List[str]]:
        effective_max = min(request.max_count, self.config.count_max)
        target_count = min(request.count, effective_max)
        warnings: List[str] = []
        if request.count > target_count:
            warnings.append(
                f"count capped from {request.count} to {target_count} by max_count policy."
            )
        return target_count, warnings

    def _generate_drafts(
        self,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> DraftGenerationResult:
        deterministic = DeterministicDraftGenerator(self)
        if request.draft_mode != "llm":
            return deterministic.generate(request, count)

        try:
            llm_generator = LLMDraftGenerator(
                repo=self.repo,
                context_builder=self.context_builder,
                adapter=self._get_llm_adapter(),
            )
            llm_result = llm_generator.generate(request, count)
        except Exception as exc:
            fallback = deterministic.generate(request, count)
            fallback.warnings.append(
                f"LLM draft_mode fallback to deterministic: {exc.__class__.__name__}."
            )
            return fallback

        if llm_result.drafts:
            return llm_result

        fallback = deterministic.generate(request, count)
        fallback.warnings.extend(llm_result.warnings)
        fallback.warnings.append(
            "LLM draft_mode returned no usable items; fallback to deterministic."
        )
        return fallback

    def _get_llm_adapter(self) -> CharacterFactLLMAdapter:
        if self.llm_adapter is None:
            self.llm_adapter = CharacterFactLLMAdapter()
        return self.llm_adapter

    def _run_draft_phase(
        self,
        request: CharacterFactGenerationRequest,
        count: int,
    ) -> List[Dict[str, Any]]:
        allowed_roles = self._read_str_list(request.constraints.get("allowed_roles"))
        tone_tags = self._normalize_string_list(request.tone_style, 3, 24)
        drafts: List[Dict[str, Any]] = []
        for index in range(1, count + 1):
            role = allowed_roles[(index - 1) % len(allowed_roles)]
            character_id = "__AUTO_ID__"
            if request.id_policy == "model":
                character_id = f"model_{index:03d}"
            tags = self._normalize_string_list([role] + tone_tags, 8, 24)
            personality_tags = self._normalize_string_list(tone_tags, 8, 24) or ["steady"]
            drafts.append(
                {
                    "character_id": character_id,
                    "name": f"{role.title()} Candidate {index}",
                    "role": role,
                    "tags": tags,
                    "attributes": {"origin": "generated", "rank": index},
                    "background": "",
                    "appearance": "",
                    "personality_tags": personality_tags,
                    "meta": {
                        "language": request.language or self.config.default_language,
                        "source": "llm",
                        "hooks": [],
                    },
                }
            )
        return drafts

    def _run_normalize_phase(
        self,
        request: CharacterFactGenerationRequest,
        drafts: Sequence[Mapping[str, Any]],
        target_count: int,
    ) -> List[Dict[str, Any]]:
        return self._normalize_batch(request, drafts, target_count)

    def _normalize_batch(
        self,
        request: CharacterFactGenerationRequest,
        drafts: Sequence[Mapping[str, Any]],
        target_count: int,
    ) -> List[Dict[str, Any]]:
        selected: List[Mapping[str, Any]] = list(drafts[:target_count])
        while len(selected) < target_count:
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

    def _allocate_character_ids(
        self,
        campaign_id: str,
        items: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        used_ids: set[str] = set()
        allocated: List[Dict[str, Any]] = []
        for item in items:
            mutable = dict(item)
            character_id = mutable.get("character_id")
            if isinstance(character_id, str):
                character_id = character_id.strip()
            else:
                character_id = ""
            if (
                character_id == "__AUTO_ID__"
                or not is_valid_character_id(character_id)
                or character_id in used_ids
                or self.repo.character_fact_id_exists(campaign_id, character_id)
            ):
                character_id = self._next_unique_character_id(campaign_id, used_ids)
            used_ids.add(character_id)
            mutable["character_id"] = character_id
            allocated.append(mutable)
        return allocated

    def _next_unique_character_id(self, campaign_id: str, used_ids: set[str]) -> str:
        for _ in range(256):
            candidate = f"ch_{uuid4().hex[:8]}"
            if candidate in used_ids:
                continue
            if self.repo.character_fact_id_exists(campaign_id, candidate):
                continue
            return candidate
        raise CharacterFactValidationError("Failed to allocate unique character_id.")

    def _validate_items(self, items: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        validated: List[Dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            try:
                validated.append(validate_character_fact(item))
            except CharacterFactSchemaError as exc:
                raise CharacterFactValidationError(
                    f"CharacterFact item[{index}] invalid: {exc}"
                ) from exc
        return validated

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
