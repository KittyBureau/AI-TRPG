from __future__ import annotations

from typing import Dict, Literal, Tuple

from pydantic import BaseModel, Field

from backend.domain.scenario_models import (
    ScenarioDifficulty,
    ScenarioLayoutType,
    ScenarioTemplateId,
)

ScenarioBootstrapAreaKind = Literal["start", "clue", "gate", "target", "transit"]
ScenarioBootstrapCompletionType = Literal["enter_area"]


class ScenarioBootstrapArea(BaseModel):
    id: str
    kind: ScenarioBootstrapAreaKind
    reachable_area_ids: Tuple[str, ...] = ()


class ScenarioBootstrapHintSource(BaseModel):
    interactable_id: str
    area_id: str
    interaction: Literal["talk"] = "talk"


class ScenarioBootstrapSearchableClueSource(BaseModel):
    interactable_id: str
    area_id: str
    interaction: Literal["search"] = "search"


class ScenarioBootstrapKeyItemGrant(BaseModel):
    item_id: str
    source_interactable_id: str
    source_area_id: str
    grant_interaction: Literal["search"] = "search"


class ScenarioBootstrapGate(BaseModel):
    interactable_id: str
    area_id: str
    from_area_id: str
    to_area_id: str
    required_item_id: str


class ScenarioBootstrapCompletion(BaseModel):
    type: ScenarioBootstrapCompletionType = "enter_area"
    target_area_id: str


class ScenarioBootstrapFragment(BaseModel):
    template_id: ScenarioTemplateId
    template_version: str = "v0"
    layout_type: ScenarioLayoutType
    difficulty: ScenarioDifficulty
    area_count: int
    start_area_id: str
    clue_area_id: str
    target_area_id: str
    areas: Dict[str, ScenarioBootstrapArea] = Field(default_factory=dict)
    hint_source: ScenarioBootstrapHintSource
    searchable_clue_source: ScenarioBootstrapSearchableClueSource
    key_item_grant: ScenarioBootstrapKeyItemGrant
    gate: ScenarioBootstrapGate
    completion: ScenarioBootstrapCompletion
