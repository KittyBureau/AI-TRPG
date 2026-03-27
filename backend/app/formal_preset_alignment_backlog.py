from __future__ import annotations

from backend.app.formal_preset_alignment_audit import (
    build_preset_alignment_audit_summary,
)
from backend.domain.formal_gameplay_model import (
    PresetAlignmentAuditItem,
    PresetAlignmentBacklogItem,
    PresetAlignmentBacklogPlan,
    PresetAlignmentBacklogSummary,
)


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_preset_alignment_backlog_summary() -> PresetAlignmentBacklogSummary:
    audit_summary = build_preset_alignment_audit_summary()
    preset_plans: list[PresetAlignmentBacklogPlan] = []
    flat_items: list[PresetAlignmentBacklogItem] = []

    for preset_summary in audit_summary.preset_summaries:
        items = _build_backlog_items_for_preset(preset_summary)
        preset_plans.append(
            PresetAlignmentBacklogPlan(
                preset_id=preset_summary.preset_id,
                alignment_level=preset_summary.alignment_level,
                priority_hint=preset_summary.priority_hint,
                items=items,
            )
        )
        flat_items.extend(items)

    preset_plans.sort(
        key=lambda plan: (_PRIORITY_ORDER[plan.priority_hint], plan.preset_id)
    )
    flat_items.sort(
        key=lambda item: (
            _PRIORITY_ORDER[item.priority_hint],
            item.preset_id,
            item.gap_type,
        )
    )

    count_by_gap_type = {
        "missing_dependency_group_alignment": 0,
        "missing_gate_clue_alignment": 0,
        "missing_authoring_audit_visibility": 0,
        "shaping_gap_unexposed": 0,
        "limited_preset_coverage_alignment": 0,
    }
    count_by_target = {
        "adapter_only": 0,
        "formal_annotation": 0,
        "future_optional": 0,
    }
    for item in flat_items:
        count_by_gap_type[item.gap_type] += 1
        count_by_target[item.recommended_target] += 1

    return PresetAlignmentBacklogSummary(
        preset_count=audit_summary.preset_count,
        total_backlog_items=len(flat_items),
        count_by_gap_type=count_by_gap_type,
        count_by_target=count_by_target,
        preset_plans=preset_plans,
        items=flat_items,
    )


def _build_backlog_items_for_preset(
    preset_summary: PresetAlignmentAuditItem,
) -> list[PresetAlignmentBacklogItem]:
    items: list[PresetAlignmentBacklogItem] = []
    if not preset_summary.has_dependency_groups:
        items.append(
            _backlog_item(
                preset_summary,
                gap_type="missing_dependency_group_alignment",
                recommended_target="adapter_only",
                rationale="formal preset output still lacks explicit dependency_group alignment.",
            )
        )
    if not preset_summary.has_clue_support_signal:
        items.append(
            _backlog_item(
                preset_summary,
                gap_type="missing_gate_clue_alignment",
                recommended_target="formal_annotation",
                rationale="critical gate paths do not yet expose stable gate_clue annotations.",
            )
        )
    if not preset_summary.has_authoring_audit:
        items.append(
            _backlog_item(
                preset_summary,
                gap_type="missing_authoring_audit_visibility",
                recommended_target="adapter_only",
                rationale="formal preset output is not yet producing stable authoring audit visibility.",
            )
        )
    if not preset_summary.has_full_area_coverage:
        items.append(
            _backlog_item(
                preset_summary,
                gap_type="limited_preset_coverage_alignment",
                recommended_target="future_optional",
                rationale="current formal preset output covers only a structurally useful sample, not the full preset area graph.",
            )
        )
    if _has_unexposed_shaping_gap(preset_summary):
        items.append(
            _backlog_item(
                preset_summary,
                gap_type="shaping_gap_unexposed",
                recommended_target="formal_annotation",
                rationale="current formal output still shows weak clue coverage without an explicit shaping gap signal.",
            )
        )
    return items


def _has_unexposed_shaping_gap(preset_summary: PresetAlignmentAuditItem) -> bool:
    if preset_summary.has_shaping_gap_signal:
        return False
    if preset_summary.overall_quality_status != "weak":
        return False
    return "clue_support_related" in preset_summary.issue_categories


def _backlog_item(
    preset_summary: PresetAlignmentAuditItem,
    *,
    gap_type: str,
    recommended_target: str,
    rationale: str,
) -> PresetAlignmentBacklogItem:
    return PresetAlignmentBacklogItem(
        preset_id=preset_summary.preset_id,
        alignment_level=preset_summary.alignment_level,
        priority_hint=preset_summary.priority_hint,
        gap_type=gap_type,
        recommended_target=recommended_target,
        rationale=rationale,
    )
