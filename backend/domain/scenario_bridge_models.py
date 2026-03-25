from __future__ import annotations

from typing import Dict, Literal, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from backend.domain.formal_gameplay_model import ValidationResult
from backend.domain.scenario_models import (
    ScenarioDifficulty,
    ScenarioLayoutType,
    ScenarioTemplateId,
)

ScenarioBridgeAreaKind = Literal["start", "clue", "gate", "target", "transit"]
ScenarioBridgeInteractableKind = Literal["hint_source", "searchable_clue_source", "gate"]
ScenarioBridgeCompletionType = Literal["enter_area"]


class ScenarioBridgeArea(BaseModel):
    id: str
    kind: ScenarioBridgeAreaKind
    reachable_area_ids: Tuple[str, ...] = ()


class ScenarioBridgeInteractable(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: ScenarioBridgeInteractableKind
    area_id: str
    reveals_item_id: str = Field(
        default="",
        validation_alias=AliasChoices("reveals_item_id", "grants_item_id"),
    )
    leads_to_area_id: str = ""

    @property
    def grants_item_id(self) -> str:
        return self.reveals_item_id


class ScenarioBridgeRevealedItem(BaseModel):
    item_id: str
    source_interactable_id: str


class ScenarioBridgeGate(BaseModel):
    from_area_id: str
    to_area_id: str
    interactable_id: str
    required_item_id: str


class ScenarioBridgeCompletion(BaseModel):
    type: ScenarioBridgeCompletionType = "enter_area"
    target_area_id: str


class ScenarioRuntimeBridge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_id: ScenarioTemplateId
    template_version: str = "v0"
    layout_type: ScenarioLayoutType
    difficulty: ScenarioDifficulty
    area_count: int
    start_area_id: str
    clue_area_id: str
    target_area_id: str
    areas: Dict[str, ScenarioBridgeArea] = Field(default_factory=dict)
    interactables: Dict[str, ScenarioBridgeInteractable] = Field(default_factory=dict)
    revealed_item: ScenarioBridgeRevealedItem = Field(
        validation_alias=AliasChoices("revealed_item", "key_item"),
    )
    gate: ScenarioBridgeGate
    completion: ScenarioBridgeCompletion
    formal_validation: ValidationResult | None = None

    @property
    def key_item(self) -> ScenarioBridgeRevealedItem:
        return self.revealed_item
