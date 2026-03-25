from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

NodeType = Literal["area", "gate", "clue_source", "item_dependency", "goal"]
EdgeType = Literal[
    "transition",
    "blocks_transition",
    "reveals",
    "requires",
    "depends_on",
    "satisfies",
    "located_in",
]
DependencyMode = Literal["all_of", "any_of"]
GoalType = Literal["enter_area", "interact_entity"]
ValidationSeverity = Literal["error", "warning"]


class Node(BaseModel):
    id: str
    type: NodeType


class Edge(BaseModel):
    from_id: str
    to_id: str
    type: EdgeType


class DependencyGroup(BaseModel):
    id: str
    mode: DependencyMode = "all_of"
    node_ids: List[str] = Field(default_factory=list)


class Goal(BaseModel):
    id: str
    type: GoalType
    target_id: str


class FormalGameplayModel(BaseModel):
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    dependency_groups: List[DependencyGroup] = Field(default_factory=list)
    goals: List[Goal] = Field(default_factory=list)
    start_area_id: str


class ValidationIssue(BaseModel):
    code: str
    severity: ValidationSeverity = "error"
    refs: Dict[str, object] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    main_path_solvable: bool = False
    issues: List[ValidationIssue] = Field(default_factory=list)
