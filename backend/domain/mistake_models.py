from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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


MistakeCategory = Literal[
    "wrong_item",
    "blocked_attempt",
    "invalid_interaction",
    "repeated_misuse",
]


class CampaignMistakeSignalCreate(BaseModel):
    category: MistakeCategory
    source_tool: str
    reason: str
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    area_id: Optional[str] = None
    item_id: Optional[str] = None
    required_item_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_tool", "reason")
    @classmethod
    def _validate_required_string(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "value")
        return _normalize_required_string(value, field_name=field_name)

    @field_validator("target_id", "target_label", "area_id", "item_id", "required_item_id")
    @classmethod
    def _validate_optional_string(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_string(value)


class CampaignMistakeSignal(CampaignMistakeSignalCreate):
    signal_id: str
    count: int = Field(default=1, ge=1)
    level: int = Field(default=1, ge=1, le=3)
    last_turn_index: int = Field(default=0, ge=0)
    last_turn_id: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("signal_id")
    @classmethod
    def _validate_signal_id(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="signal_id")

    @field_validator("last_turn_id")
    @classmethod
    def _validate_last_turn_id(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_string(value)


class CampaignMistakeState(BaseModel):
    total_count: int = Field(default=0, ge=0)
    level: int = Field(default=0, ge=0, le=3)
    last_turn_index: int = Field(default=0, ge=0)
    entries: Dict[str, CampaignMistakeSignal] = Field(default_factory=dict)
