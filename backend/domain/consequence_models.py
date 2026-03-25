from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.domain.mistake_models import MistakeCategory


def _normalize_required_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_string_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)
    return normalized


ConsequenceType = Literal["area_pressure", "guarded_response"]
ConsequenceScopeKind = Literal["area", "npc", "target"]
ConsequenceTone = Literal["watchful", "tense", "guarded", "cold"]


class CampaignConsequenceCreate(BaseModel):
    type: ConsequenceType
    scope_kind: ConsequenceScopeKind
    level: int = Field(default=1, ge=1, le=2)
    source_categories: list[MistakeCategory] = Field(default_factory=list)
    source_signal_ids: list[str] = Field(default_factory=list)
    area_id: Optional[str] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    tone: ConsequenceTone
    narrative_hint: str
    last_turn_index: int = Field(default=0, ge=0)

    @field_validator("area_id", "target_id", "target_label")
    @classmethod
    def _validate_optional_string(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_string(value)

    @field_validator("source_categories")
    @classmethod
    def _validate_source_categories(
        cls, values: list[MistakeCategory]
    ) -> list[MistakeCategory]:
        return list(_normalize_string_list([str(value) for value in values]))

    @field_validator("source_signal_ids")
    @classmethod
    def _validate_source_signal_ids(cls, values: list[str]) -> list[str]:
        return _normalize_string_list(values)

    @field_validator("narrative_hint")
    @classmethod
    def _validate_narrative_hint(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="narrative_hint")

    @model_validator(mode="after")
    def _validate_scope_requirements(self) -> "CampaignConsequenceCreate":
        if self.scope_kind == "area":
            if not isinstance(self.area_id, str) or not self.area_id.strip():
                raise ValueError("area_id is required for area consequences")
            self.target_id = _normalize_optional_string(self.target_id)
            return self
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError("target_id is required for target or npc consequences")
        return self


class CampaignConsequence(CampaignConsequenceCreate):
    consequence_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("consequence_id")
    @classmethod
    def _validate_consequence_id(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="consequence_id")


class CampaignConsequenceState(BaseModel):
    level: int = Field(default=0, ge=0, le=2)
    last_turn_index: int = Field(default=0, ge=0)
    entries: dict[str, CampaignConsequence] = Field(default_factory=dict)
