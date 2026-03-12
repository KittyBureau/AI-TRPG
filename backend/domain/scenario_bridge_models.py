from __future__ import annotations

from typing import Dict, Literal, Tuple

from pydantic import BaseModel, Field

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
    id: str
    kind: ScenarioBridgeInteractableKind
    area_id: str
    grants_item_id: str = ""
    requires_item_id: str = ""
    leads_to_area_id: str = ""


class ScenarioBridgeKeyItem(BaseModel):
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
    key_item: ScenarioBridgeKeyItem
    gate: ScenarioBridgeGate
    completion: ScenarioBridgeCompletion
