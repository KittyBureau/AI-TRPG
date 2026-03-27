from __future__ import annotations

from typing import Any, Dict, Literal, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

ScenarioTemplateId = Literal["key_gate_scenario"]
ScenarioLayoutType = Literal["linear", "branch"]
ScenarioDifficulty = Literal["easy", "standard"]
ScenarioGoalType = Literal["enter_area"]
ScenarioDependencyMode = Literal["all_of", "any_of"]
ScenarioAreaKind = Literal["start", "clue", "gate", "target", "transit"]
ScenarioEntityKind = Literal["hint_source", "clue_source", "gate"]
ScenarioItemKind = Literal["required_item"]
ScenarioStructuralRole = Literal[
    "start_area",
    "hint_source",
    "clue_area",
    "clue_source",
    "revealed_item",
    "gate_area",
    "gate_entity",
    "required_item",
    "target_area",
]


class ScenarioParams(BaseModel):
    scenario_template: ScenarioTemplateId
    theme: str
    area_count: int
    layout_type: ScenarioLayoutType
    difficulty: ScenarioDifficulty


class ScenarioTemplateDefinition(BaseModel):
    template_id: ScenarioTemplateId
    template_version: str = "v0"
    description: str = ""
    default_theme: str
    default_area_count: int = 6
    min_area_count: int = 4
    max_area_count: int = 8
    default_layout_type: ScenarioLayoutType = "branch"
    default_difficulty: ScenarioDifficulty = "easy"
    allowed_layout_types: Tuple[ScenarioLayoutType, ...] = ("linear", "branch")
    allowed_difficulties: Tuple[ScenarioDifficulty, ...] = ("easy", "standard")
    required_roles: Tuple[ScenarioStructuralRole, ...]
    has_hint_source: bool = True


class ScenarioRoleAssignments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_area_id: str = ""
    hint_source_id: str = ""
    clue_area_id: str = ""
    clue_source_id: str = ""
    revealed_item_id: str = Field(
        default="",
        validation_alias=AliasChoices("revealed_item_id", "granted_item_id"),
    )
    gate_area_id: str = ""
    gate_entity_id: str = ""
    required_item_id: str = ""
    target_area_id: str = ""

    @property
    def granted_item_id(self) -> str:
        return self.revealed_item_id


class ScenarioGateRule(BaseModel):
    from_area_id: str
    to_area_id: str
    required_item_id: str
    gate_entity_id: str
    dependency_group_id: str = ""


class ScenarioGoalRule(BaseModel):
    type: ScenarioGoalType = "enter_area"
    target_area_id: str


class ScenarioDependencyGroup(BaseModel):
    id: str
    mode: ScenarioDependencyMode = "all_of"
    node_ids: Tuple[str, ...] = ()


class ScenarioArea(BaseModel):
    id: str
    kind: ScenarioAreaKind
    connected_area_ids: Tuple[str, ...] = ()


class ScenarioEntity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: ScenarioEntityKind
    area_id: str
    reveals_item_id: str = Field(
        default="",
        validation_alias=AliasChoices("reveals_item_id", "grants_item_id"),
    )

    @property
    def grants_item_id(self) -> str:
        return self.reveals_item_id


class ScenarioItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: ScenarioItemKind = "required_item"
    revealed_by_entity_id: str = Field(
        validation_alias=AliasChoices("revealed_by_entity_id", "granted_by_entity_id"),
    )
    required_by_gate_entity_id: str

    @property
    def granted_by_entity_id(self) -> str:
        return self.revealed_by_entity_id


class ScenarioTopology(BaseModel):
    area_ids_in_order: Tuple[str, ...] = ()
    main_path_area_ids: Tuple[str, ...] = ()
    branch_area_ids: Tuple[str, ...] = ()
    areas: Dict[str, ScenarioArea] = Field(default_factory=dict)


class MaterializedScenario(BaseModel):
    template_id: ScenarioTemplateId
    template_version: str = "v0"
    params: ScenarioParams
    roles: ScenarioRoleAssignments
    topology: ScenarioTopology
    entities: Dict[str, ScenarioEntity] = Field(default_factory=dict)
    items: Dict[str, ScenarioItem] = Field(default_factory=dict)
    dependency_groups: Dict[str, ScenarioDependencyGroup] = Field(default_factory=dict)
    gate_rule: ScenarioGateRule
    goal_rule: ScenarioGoalRule


class ScenarioValidationResult(BaseModel):
    ok: bool = True
    template_id: ScenarioTemplateId
    checked_area_count: int
    issues: Tuple["ScenarioValidationIssue", ...] = ()


class ScenarioValidationIssue(BaseModel):
    code: str
    message: str
    refs: Dict[str, Any] = Field(default_factory=dict)
