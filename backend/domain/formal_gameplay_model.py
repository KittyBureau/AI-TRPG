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
ClueType = Literal["critical", "optional"]
QualityStatus = Literal["good", "weak", "failing"]
IssueCategory = Literal[
    "solvability_related",
    "path_coverage_related",
    "clue_support_related",
    "shaping_gap_related",
]
AlignmentLevel = Literal["legacy", "partial", "aligned"]
PriorityHint = Literal["high", "medium", "low"]
GapType = Literal[
    "missing_dependency_group_alignment",
    "missing_gate_clue_alignment",
    "missing_authoring_audit_visibility",
    "shaping_gap_unexposed",
]
RemediationTarget = Literal["adapter_only", "formal_annotation", "future_optional"]
ValidationSeverity = Literal["error", "warning"]


class Node(BaseModel):
    id: str
    type: NodeType
    dependency_group_id: str | None = None


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


class GateClue(BaseModel):
    clue_id: str
    gate_id: str
    supported_items: List[str] = Field(default_factory=list)
    clue_type: ClueType = "critical"


class GateClueSupportGap(BaseModel):
    gate_id: str
    item_id: str
    reason: str = "missing_inferred_clue_source"
    source: str = "generator_fallback"


class FormalGameplayModel(BaseModel):
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    dependency_groups: List[DependencyGroup] = Field(default_factory=list)
    gate_clues: List[GateClue] = Field(default_factory=list)
    gate_clue_support_gaps: List[GateClueSupportGap] = Field(default_factory=list)
    goals: List[Goal] = Field(default_factory=list)
    start_area_id: str


class ValidationIssue(BaseModel):
    code: str
    severity: ValidationSeverity = "error"
    refs: Dict[str, object] = Field(default_factory=dict)


class GateQualitySummary(BaseModel):
    gate_id: str
    quality_status: QualityStatus = "good"


class GateAuthoringAudit(BaseModel):
    gate_id: str
    quality_status: QualityStatus = "good"
    issue_categories: List[IssueCategory] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    has_shaping_gap: bool = False


class OverallAuthoringAuditSummary(BaseModel):
    overall_quality_status: QualityStatus = "good"
    gate_count_by_quality: Dict[QualityStatus, int] = Field(default_factory=dict)
    issue_count_by_category: Dict[IssueCategory, int] = Field(default_factory=dict)
    gates_with_shaping_gaps: List[str] = Field(default_factory=list)


class PresetAlignmentAuditItem(BaseModel):
    preset_id: str
    alignment_level: AlignmentLevel = "legacy"
    priority_hint: PriorityHint = "high"
    key_findings: List[str] = Field(default_factory=list)
    has_dependency_groups: bool = False
    has_clue_support_signal: bool = False
    has_shaping_gap_signal: bool = False
    has_authoring_audit: bool = False
    overall_quality_status: QualityStatus = "good"


class PresetAlignmentAuditSummary(BaseModel):
    preset_count: int = 0
    count_by_alignment_level: Dict[AlignmentLevel, int] = Field(default_factory=dict)
    count_by_priority: Dict[PriorityHint, int] = Field(default_factory=dict)
    preset_summaries: List[PresetAlignmentAuditItem] = Field(default_factory=list)


class PresetAlignmentBacklogItem(BaseModel):
    preset_id: str
    alignment_level: AlignmentLevel = "legacy"
    priority_hint: PriorityHint = "high"
    gap_type: GapType
    recommended_target: RemediationTarget
    rationale: str = ""


class PresetAlignmentBacklogPlan(BaseModel):
    preset_id: str
    alignment_level: AlignmentLevel = "legacy"
    priority_hint: PriorityHint = "high"
    items: List[PresetAlignmentBacklogItem] = Field(default_factory=list)


class PresetAlignmentBacklogSummary(BaseModel):
    preset_count: int = 0
    total_backlog_items: int = 0
    count_by_gap_type: Dict[GapType, int] = Field(default_factory=dict)
    count_by_target: Dict[RemediationTarget, int] = Field(default_factory=dict)
    preset_plans: List[PresetAlignmentBacklogPlan] = Field(default_factory=list)
    items: List[PresetAlignmentBacklogItem] = Field(default_factory=list)


class ValidationResult(BaseModel):
    main_path_solvable: bool = False
    gate_quality_statuses: List[GateQualitySummary] = Field(default_factory=list)
    overall_quality_status: QualityStatus = "good"
    gate_authoring_audits: List[GateAuthoringAudit] = Field(default_factory=list)
    overall_authoring_audit: OverallAuthoringAuditSummary = Field(
        default_factory=OverallAuthoringAuditSummary
    )
    issues: List[ValidationIssue] = Field(default_factory=list)
