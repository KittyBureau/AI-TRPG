from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MapArea(BaseModel):
    id: str
    name: str
    description: str = ""
    parent_area_id: Optional[str] = None
    reachable_area_ids: List[str] = Field(default_factory=list)


class MapConnection(BaseModel):
    from_area_id: str
    to_area_id: str


class MapData(BaseModel):
    areas: Dict[str, MapArea] = Field(default_factory=dict)
    connections: List[MapConnection] = Field(default_factory=list)


class Selected(BaseModel):
    world_id: str
    map_id: str
    party_character_ids: List[str]
    active_actor_id: str


class ContextSettings(BaseModel):
    full_context_enabled: bool = True
    compress_enabled: bool = False


class DialogSettings(BaseModel):
    auto_type_enabled: bool = True
    strict_semantic_guard: bool = False
    conflict_text_checks_enabled: bool = False
    turn_profile_trace_enabled: bool = False


class RulesSettings(BaseModel):
    hp_zero_ends_game: bool = True


class RollbackSettings(BaseModel):
    max_checkpoints: int = 0


class CharacterFactGenerationSettings(BaseModel):
    draft_mode: str = "deterministic"


class CharactersSettings(BaseModel):
    fact_generation: CharacterFactGenerationSettings = Field(
        default_factory=CharacterFactGenerationSettings
    )


class SettingsSnapshot(BaseModel):
    context: ContextSettings = Field(default_factory=ContextSettings)
    rules: RulesSettings = Field(default_factory=RulesSettings)
    rollback: RollbackSettings = Field(default_factory=RollbackSettings)
    dialog: DialogSettings = Field(default_factory=DialogSettings)
    characters: CharactersSettings = Field(default_factory=CharactersSettings)


class Goal(BaseModel):
    text: str
    status: str


class Milestone(BaseModel):
    current: str
    last_advanced_turn: int = 0
    turn_trigger_interval: int = 6
    pressure: int = 0
    pressure_threshold: int = 2
    summary: str = ""


class CampaignLifecycle(BaseModel):
    ended: bool = False
    reason: Optional[str] = None
    ended_at: Optional[str] = None


class CampaignState(BaseModel):
    positions: Dict[str, str] = Field(default_factory=dict)
    positions_parent: Dict[str, str] = Field(default_factory=dict)
    positions_child: Dict[str, Optional[str]] = Field(default_factory=dict)


class EntityLocation(BaseModel):
    type: Literal["area", "actor", "entity"]
    id: str


class Entity(BaseModel):
    id: str
    kind: str = "object"
    label: str
    tags: List[str] = Field(default_factory=list)
    loc: EntityLocation
    verbs: List[str] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)
    props: Dict[str, Any] = Field(default_factory=dict)


class RuntimeItemStack(BaseModel):
    stack_id: str
    definition_id: str
    quantity: int = 1
    parent_type: Literal["actor", "area", "item"]
    parent_id: str
    label: str = ""
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    verbs: List[str] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)
    props: Dict[str, Any] = Field(default_factory=dict)
    stackable: bool = True
    is_container: bool = False


class ActorState(BaseModel):
    position: Optional[str] = None
    hp: int = 10
    character_state: str = "alive"
    inventory: Dict[str, int] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)


class Campaign(BaseModel):
    id: str
    selected: Selected
    settings_snapshot: SettingsSnapshot = Field(default_factory=SettingsSnapshot)
    settings_revision: int = 0
    allowlist: List[str] = Field(
        default_factory=lambda: [
            "move",
            "hp_delta",
            "inventory_add",
            "map_generate",
            "move_options",
            "world_generate",
            "actor_spawn",
            "scene_action",
        ]
    )
    map: MapData = Field(default_factory=MapData)
    state: CampaignState = Field(default_factory=CampaignState)
    actors: Dict[str, ActorState] = Field(default_factory=dict)
    items: Dict[str, RuntimeItemStack] = Field(default_factory=dict)
    entities: Dict[str, Entity] = Field(default_factory=dict)
    positions: Dict[str, str] = Field(default_factory=dict)
    hp: Dict[str, int] = Field(default_factory=dict)
    character_states: Dict[str, str] = Field(default_factory=dict)
    goal: Goal
    milestone: Milestone
    lifecycle: CampaignLifecycle = Field(default_factory=CampaignLifecycle)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ToolCall(BaseModel):
    id: str
    tool: str
    args: Dict[str, Any]
    reason: Optional[str] = None


class AssistantStructured(BaseModel):
    tool_calls: List[ToolCall] = Field(default_factory=list)


class AppliedAction(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: str


class FailedCall(BaseModel):
    id: str
    tool: str
    status: str
    reason: str


class ToolFeedback(BaseModel):
    failed_calls: List[FailedCall] = Field(default_factory=list)


class ConflictItem(BaseModel):
    type: str
    field: str
    expected: Any
    found_in_text: str


class ConflictReport(BaseModel):
    retries: int
    conflicts: List[ConflictItem] = Field(default_factory=list)


class StateSummary(BaseModel):
    active_actor_id: str
    positions: Dict[str, str] = Field(default_factory=dict)
    positions_parent: Dict[str, str] = Field(default_factory=dict)
    positions_child: Dict[str, Optional[str]] = Field(default_factory=dict)
    hp: Dict[str, int] = Field(default_factory=dict)
    character_states: Dict[str, str] = Field(default_factory=dict)
    inventories: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    inventory_stack_ids: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)
    objective: str = ""
    active_area_id: Optional[str] = None
    active_area_name: str = ""
    active_area_description: str = ""
    active_actor_inventory: Dict[str, int] = Field(default_factory=dict)
    active_actor_inventory_stack_ids: Dict[str, List[str]] = Field(default_factory=dict)


class TurnLogEntry(BaseModel):
    turn_id: str
    timestamp: str
    user_input: str
    dialog_type: str
    dialog_type_source: str
    settings_revision: int
    assistant_text: str
    assistant_structured: AssistantStructured
    applied_actions: List[AppliedAction] = Field(default_factory=list)
    tool_feedback: Optional[ToolFeedback] = None
    conflict_report: Optional[ConflictReport] = None
    state_summary: StateSummary


class CampaignSummary(BaseModel):
    id: str
    world_id: str
    active_actor_id: str
