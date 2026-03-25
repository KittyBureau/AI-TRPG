from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_FACT_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,127}$")
_FACT_TYPE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{1,63}$")


def _read_required_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _read_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class FactSource(BaseModel):
    kind: Literal["manual", "llm", "tool", "system", "import"] = "llm"
    ref_id: Optional[str] = None
    actor_id: Optional[str] = None

    @field_validator("ref_id", "actor_id")
    @classmethod
    def _normalize_optional_id(cls, value: Optional[str]) -> Optional[str]:
        return _read_optional_string(value)


class FactScope(BaseModel):
    kind: Literal["campaign", "area", "npc", "entity", "actor", "item"] = "campaign"
    ref_id: Optional[str] = None

    @field_validator("ref_id")
    @classmethod
    def _normalize_optional_id(cls, value: Optional[str]) -> Optional[str]:
        return _read_optional_string(value)

    @model_validator(mode="after")
    def _validate_scope_ref(self) -> "FactScope":
        if self.kind == "campaign":
            self.ref_id = None
            return self
        if not isinstance(self.ref_id, str) or not self.ref_id.strip():
            raise ValueError(f"scope.ref_id is required for scope kind: {self.kind}")
        return self


class CampaignFactCreate(BaseModel):
    fact_id: Optional[str] = None
    fact_type: str
    summary: str
    content: str = ""
    source: FactSource = Field(default_factory=FactSource)
    authority: Literal["authoritative", "uncertain"] = "uncertain"
    reliability: Literal["confirmed", "reported", "generated"] = "generated"
    scope: FactScope = Field(default_factory=FactScope)
    lifecycle: Literal["persistent", "temporary"] = "persistent"
    expires_turn_index: Optional[int] = Field(default=None, ge=0)
    created_turn_index: Optional[int] = Field(default=None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("fact_id")
    @classmethod
    def _normalize_fact_id(cls, value: Optional[str]) -> Optional[str]:
        normalized = _read_optional_string(value)
        if normalized is None:
            return None
        if _FACT_ID_PATTERN.fullmatch(normalized) is None:
            raise ValueError("fact_id format is invalid")
        return normalized

    @field_validator("fact_type")
    @classmethod
    def _normalize_fact_type(cls, value: str) -> str:
        normalized = _read_required_string(value, field_name="fact_type")
        if _FACT_TYPE_PATTERN.fullmatch(normalized) is None:
            raise ValueError("fact_type format is invalid")
        return normalized

    @field_validator("summary")
    @classmethod
    def _normalize_summary(cls, value: str) -> str:
        return _read_required_string(value, field_name="summary")

    @field_validator("content")
    @classmethod
    def _normalize_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _normalize_lifecycle(self) -> "CampaignFactCreate":
        if self.lifecycle == "persistent":
            self.expires_turn_index = None
        return self


class CampaignFact(CampaignFactCreate):
    fact_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
