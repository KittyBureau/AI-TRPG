from __future__ import annotations

from backend.app.formal_preset_mapper import (
    build_formal_model_from_preset,
    list_supported_preset_world_ids,
)
from backend.app.formal_validator import validate_formal_model
from backend.app.world_presets import build_campaign_world_preset
from backend.domain.formal_gameplay_model import (
    PresetAlignmentAuditItem,
    PresetAlignmentAuditSummary,
)


def build_preset_alignment_audit_summary() -> PresetAlignmentAuditSummary:
    preset_summaries: list[PresetAlignmentAuditItem] = []
    for preset_id in list_supported_preset_world_ids():
        preset = build_campaign_world_preset(preset_id)
        if preset is None:
            continue
        formal_model = build_formal_model_from_preset(preset_id, preset)
        if formal_model is None:
            continue

        validation = preset.formal_validation or validate_formal_model(formal_model)
        has_dependency_groups = bool(formal_model.dependency_groups)
        has_clue_support_signal = bool(formal_model.gate_clues)
        has_shaping_gap_signal = bool(formal_model.gate_clue_support_gaps)
        has_authoring_audit = bool(validation.gate_authoring_audits)

        alignment_level = _derive_alignment_level(
            has_dependency_groups=has_dependency_groups,
            has_clue_support_signal=has_clue_support_signal,
            has_shaping_gap_signal=has_shaping_gap_signal,
            has_authoring_audit=has_authoring_audit,
        )
        priority_hint = _derive_priority_hint(alignment_level)
        key_findings = _build_key_findings(
            alignment_level=alignment_level,
            has_dependency_groups=has_dependency_groups,
            has_clue_support_signal=has_clue_support_signal,
            has_shaping_gap_signal=has_shaping_gap_signal,
            has_authoring_audit=has_authoring_audit,
            overall_quality_status=validation.overall_quality_status,
        )

        preset_summaries.append(
            PresetAlignmentAuditItem(
                preset_id=preset_id,
                alignment_level=alignment_level,
                priority_hint=priority_hint,
                key_findings=key_findings,
                has_dependency_groups=has_dependency_groups,
                has_clue_support_signal=has_clue_support_signal,
                has_shaping_gap_signal=has_shaping_gap_signal,
                has_authoring_audit=has_authoring_audit,
                overall_quality_status=validation.overall_quality_status,
            )
        )

    preset_summaries.sort(key=lambda item: item.preset_id)
    count_by_alignment_level = {"legacy": 0, "partial": 0, "aligned": 0}
    count_by_priority = {"high": 0, "medium": 0, "low": 0}
    for item in preset_summaries:
        count_by_alignment_level[item.alignment_level] += 1
        count_by_priority[item.priority_hint] += 1

    return PresetAlignmentAuditSummary(
        preset_count=len(preset_summaries),
        count_by_alignment_level=count_by_alignment_level,
        count_by_priority=count_by_priority,
        preset_summaries=preset_summaries,
    )


def _derive_alignment_level(
    *,
    has_dependency_groups: bool,
    has_clue_support_signal: bool,
    has_shaping_gap_signal: bool,
    has_authoring_audit: bool,
) -> str:
    if (
        has_dependency_groups
        and has_authoring_audit
        and (has_clue_support_signal or has_shaping_gap_signal)
    ):
        return "aligned"
    if (
        not has_dependency_groups
        and not has_clue_support_signal
        and not has_shaping_gap_signal
    ):
        return "legacy"
    return "partial"


def _derive_priority_hint(alignment_level: str) -> str:
    if alignment_level == "legacy":
        return "high"
    if alignment_level == "partial":
        return "medium"
    return "low"


def _build_key_findings(
    *,
    alignment_level: str,
    has_dependency_groups: bool,
    has_clue_support_signal: bool,
    has_shaping_gap_signal: bool,
    has_authoring_audit: bool,
    overall_quality_status: str,
) -> list[str]:
    findings: list[str] = [f"alignment_level:{alignment_level}"]
    findings.append(
        "dependency_groups_present"
        if has_dependency_groups
        else "dependency_groups_missing"
    )
    findings.append(
        "clue_support_signals_present"
        if has_clue_support_signal
        else "clue_support_signals_missing"
    )
    findings.append(
        "authoring_audit_available"
        if has_authoring_audit
        else "authoring_audit_missing"
    )
    if has_shaping_gap_signal:
        findings.append("shaping_gap_signals_present")
    findings.append(f"overall_quality:{overall_quality_status}")
    return findings
