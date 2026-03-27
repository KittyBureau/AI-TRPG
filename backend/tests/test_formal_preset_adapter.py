from __future__ import annotations

from backend.app.formal_preset_alignment_audit import (
    build_preset_alignment_audit_summary,
)
from backend.app.formal_preset_alignment_backlog import (
    build_preset_alignment_backlog_summary,
)
import backend.app.formal_preset_alignment_backlog as preset_backlog_module
from backend.app.formal_preset_mapper import build_formal_model_from_preset
from backend.app.formal_validator import validate_formal_model
from backend.app.turn_service import TurnService
from backend.domain.formal_gameplay_model import (
    PresetAlignmentAuditItem,
    PresetAlignmentAuditSummary,
)
from backend.app.world_presets import (
    MIDNIGHT_ARCHIVE_WORLD_ID,
    TEST_WATCHTOWER_WORLD_ID,
    build_campaign_world_preset,
)
from backend.infra.file_repo import FileRepo


def test_watchtower_preset_formal_mapping_builds_expected_structure() -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(TEST_WATCHTOWER_WORLD_ID, preset)

    assert model is not None
    node_types = {node.id: node.type for node in model.nodes}
    assert node_types["watchtower_door"] == "gate"
    assert node_types["old_hut_clue"] == "clue_source"
    assert node_types["tower_key"] == "item_dependency"
    assert all(node.type != "goal" for node in model.nodes)
    assert model.goals[0].type == "enter_area"
    assert model.goals[0].target_id == "watchtower_inside"


def test_watchtower_preset_validation_is_solvable() -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(TEST_WATCHTOWER_WORLD_ID, preset)
    assert model is not None
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.issues == []


def test_midnight_archive_preset_formal_mapping_builds_expected_structure() -> None:
    preset = build_campaign_world_preset(MIDNIGHT_ARCHIVE_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(MIDNIGHT_ARCHIVE_WORLD_ID, preset)

    assert model is not None
    node_types = {node.id: node.type for node in model.nodes}
    assert node_types["returns_cart"] == "clue_source"
    assert node_types["routing_slip"] == "item_dependency"
    assert node_types["midnight_archive_service_gate"] == "gate"
    assert node_types["forged_file_shelf"] == "goal"
    gate_nodes = [node for node in model.nodes if node.id == "midnight_archive_service_gate"]
    assert len(gate_nodes) == 1
    assert gate_nodes[0].dependency_group_id == "dep_group:midnight_archive_service_gate"
    assert len(model.dependency_groups) == 1
    assert model.dependency_groups[0].id == "dep_group:midnight_archive_service_gate"
    assert model.dependency_groups[0].mode == "all_of"
    assert model.dependency_groups[0].node_ids == ["routing_slip"]
    assert len(model.gate_clues) == 1
    assert model.gate_clues[0].clue_id == "returns_cart"
    assert model.gate_clues[0].gate_id == "midnight_archive_service_gate"
    assert model.gate_clues[0].supported_items == ["routing_slip"]
    assert model.gate_clue_support_gaps == []
    assert model.goals[0].type == "interact_entity"
    assert model.goals[0].target_id == "forged_file_shelf"


def test_midnight_archive_preset_validation_is_solvable() -> None:
    preset = build_campaign_world_preset(MIDNIGHT_ARCHIVE_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(MIDNIGHT_ARCHIVE_WORLD_ID, preset)
    assert model is not None
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.issues == []
    assert result.overall_quality_status == "good"
    assert len(result.gate_quality_statuses) == 1
    assert result.gate_quality_statuses[0].gate_id == "midnight_archive_service_gate"
    assert result.gate_quality_statuses[0].quality_status == "good"
    assert len(result.gate_authoring_audits) == 1
    assert result.gate_authoring_audits[0].gate_id == "midnight_archive_service_gate"
    assert result.gate_authoring_audits[0].quality_status == "good"
    assert result.gate_authoring_audits[0].issue_categories == []
    assert result.gate_authoring_audits[0].issues == []
    assert result.gate_authoring_audits[0].has_shaping_gap is False
    assert result.overall_authoring_audit.overall_quality_status == "good"
    assert result.overall_authoring_audit.gate_count_by_quality == {
        "good": 1,
        "weak": 0,
        "failing": 0,
    }
    assert result.overall_authoring_audit.issue_count_by_category == {
        "solvability_related": 0,
        "path_coverage_related": 0,
        "clue_support_related": 0,
        "shaping_gap_related": 0,
    }
    assert result.overall_authoring_audit.gates_with_shaping_gaps == []


def test_midnight_archive_preset_attaches_authoring_audit_on_formal_validation() -> None:
    preset = build_campaign_world_preset(MIDNIGHT_ARCHIVE_WORLD_ID)
    assert preset is not None
    assert preset.formal_validation is not None

    assert preset.formal_validation.main_path_solvable is True
    assert preset.formal_validation.overall_quality_status == "good"
    assert len(preset.formal_validation.gate_authoring_audits) == 1
    assert preset.formal_validation.gate_authoring_audits[0].gate_id == (
        "midnight_archive_service_gate"
    )
    assert preset.formal_validation.gate_authoring_audits[0].quality_status == "good"
    assert preset.formal_validation.gate_authoring_audits[0].issue_categories == []


def test_preset_formal_validation_attaches_without_changing_bootstrap_behavior(
    tmp_path,
) -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None
    assert preset.formal_validation is not None
    assert preset.formal_validation.main_path_solvable is True

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    campaign = repo.get_campaign(campaign_id)
    assert campaign.actors["pc_001"].position == preset.start_area_id
    assert campaign.goal.text == preset.goal_text


def test_preset_alignment_audit_summary_enumerates_supported_presets() -> None:
    summary = build_preset_alignment_audit_summary()

    assert summary.preset_count >= 2
    assert summary.count_by_alignment_level == {
        "legacy": 1,
        "partial": 1,
        "aligned": 0,
    }
    assert summary.count_by_priority == {
        "high": 1,
        "medium": 1,
        "low": 0,
    }
    assert {item.preset_id for item in summary.preset_summaries} == {
        MIDNIGHT_ARCHIVE_WORLD_ID,
        TEST_WATCHTOWER_WORLD_ID,
    }


def test_preset_alignment_audit_marks_midnight_archive_as_partial_sample() -> None:
    summary = build_preset_alignment_audit_summary()
    midnight_archive = next(
        item
        for item in summary.preset_summaries
        if item.preset_id == MIDNIGHT_ARCHIVE_WORLD_ID
    )

    assert midnight_archive.alignment_level == "partial"
    assert midnight_archive.priority_hint == "medium"
    assert midnight_archive.has_dependency_groups is True
    assert midnight_archive.has_clue_support_signal is True
    assert midnight_archive.has_shaping_gap_signal is False
    assert midnight_archive.has_authoring_audit is True
    assert midnight_archive.has_full_area_coverage is False
    assert midnight_archive.issue_categories == []
    assert midnight_archive.overall_quality_status == "good"
    assert "dependency_groups_present" in midnight_archive.key_findings
    assert "clue_support_signals_present" in midnight_archive.key_findings
    assert "area_coverage_partial" in midnight_archive.key_findings


def test_preset_alignment_audit_marks_watchtower_as_legacy_expression() -> None:
    summary = build_preset_alignment_audit_summary()
    watchtower = next(
        item
        for item in summary.preset_summaries
        if item.preset_id == TEST_WATCHTOWER_WORLD_ID
    )

    assert watchtower.alignment_level == "legacy"
    assert watchtower.priority_hint == "high"
    assert watchtower.has_dependency_groups is False
    assert watchtower.has_clue_support_signal is False
    assert watchtower.has_shaping_gap_signal is False
    assert watchtower.has_authoring_audit is True
    assert watchtower.has_full_area_coverage is True
    assert watchtower.issue_categories == []
    assert watchtower.overall_quality_status == "good"
    assert "dependency_groups_missing" in watchtower.key_findings
    assert "clue_support_signals_missing" in watchtower.key_findings
    assert "area_coverage_full" in watchtower.key_findings


def test_preset_alignment_backlog_summary_enumerates_structured_items() -> None:
    summary = build_preset_alignment_backlog_summary()

    assert summary.preset_count >= 2
    assert summary.total_backlog_items >= 3
    assert summary.count_by_gap_type == {
        "missing_dependency_group_alignment": 1,
        "missing_gate_clue_alignment": 1,
        "missing_authoring_audit_visibility": 0,
        "shaping_gap_unexposed": 0,
        "limited_preset_coverage_alignment": 1,
    }
    assert summary.count_by_target == {
        "adapter_only": 1,
        "formal_annotation": 1,
        "future_optional": 1,
    }
    assert [plan.preset_id for plan in summary.preset_plans] == [
        TEST_WATCHTOWER_WORLD_ID,
        MIDNIGHT_ARCHIVE_WORLD_ID,
    ]


def test_preset_alignment_backlog_marks_midnight_archive_as_partial_future_work() -> None:
    summary = build_preset_alignment_backlog_summary()
    midnight_archive = next(
        plan
        for plan in summary.preset_plans
        if plan.preset_id == MIDNIGHT_ARCHIVE_WORLD_ID
    )

    assert midnight_archive.alignment_level == "partial"
    assert midnight_archive.priority_hint == "medium"
    assert [item.gap_type for item in midnight_archive.items] == [
        "limited_preset_coverage_alignment"
    ]
    assert [item.recommended_target for item in midnight_archive.items] == [
        "future_optional"
    ]


def test_preset_alignment_backlog_marks_watchtower_for_adapter_and_annotation_work() -> None:
    summary = build_preset_alignment_backlog_summary()
    watchtower = next(
        plan
        for plan in summary.preset_plans
        if plan.preset_id == TEST_WATCHTOWER_WORLD_ID
    )

    assert watchtower.alignment_level == "legacy"
    assert watchtower.priority_hint == "high"
    assert [item.gap_type for item in watchtower.items] == [
        "missing_dependency_group_alignment",
        "missing_gate_clue_alignment",
    ]
    assert [item.recommended_target for item in watchtower.items] == [
        "adapter_only",
        "formal_annotation",
    ]


def test_preset_alignment_backlog_exposes_missing_authoring_audit_visibility(
    monkeypatch,
) -> None:
    synthetic_summary = PresetAlignmentAuditSummary(
        preset_count=1,
        count_by_alignment_level={"legacy": 0, "partial": 1, "aligned": 0},
        count_by_priority={"high": 0, "medium": 1, "low": 0},
        preset_summaries=[
            PresetAlignmentAuditItem(
                preset_id="preset_missing_audit",
                alignment_level="partial",
                priority_hint="medium",
                key_findings=[
                    "alignment_level:partial",
                    "dependency_groups_present",
                    "clue_support_signals_present",
                    "authoring_audit_missing",
                    "area_coverage_full",
                    "overall_quality:good",
                ],
                has_dependency_groups=True,
                has_clue_support_signal=True,
                has_shaping_gap_signal=False,
                has_authoring_audit=False,
                has_full_area_coverage=True,
                issue_categories=[],
                overall_quality_status="good",
            )
        ],
    )
    monkeypatch.setattr(
        preset_backlog_module,
        "build_preset_alignment_audit_summary",
        lambda: synthetic_summary,
    )

    summary = build_preset_alignment_backlog_summary()

    assert summary.total_backlog_items == 1
    assert summary.count_by_gap_type["missing_authoring_audit_visibility"] == 1
    assert summary.items[0].gap_type == "missing_authoring_audit_visibility"
    assert summary.items[0].recommended_target == "adapter_only"


def test_preset_alignment_backlog_only_exposes_shaping_gap_unexposed_for_clue_support_issues(
    monkeypatch,
) -> None:
    synthetic_summary = PresetAlignmentAuditSummary(
        preset_count=2,
        count_by_alignment_level={"legacy": 0, "partial": 2, "aligned": 0},
        count_by_priority={"high": 0, "medium": 2, "low": 0},
        preset_summaries=[
            PresetAlignmentAuditItem(
                preset_id="preset_path_weak_only",
                alignment_level="partial",
                priority_hint="medium",
                key_findings=["overall_quality:weak"],
                has_dependency_groups=True,
                has_clue_support_signal=True,
                has_shaping_gap_signal=False,
                has_authoring_audit=True,
                has_full_area_coverage=True,
                issue_categories=["path_coverage_related"],
                overall_quality_status="weak",
            ),
            PresetAlignmentAuditItem(
                preset_id="preset_clue_weak_only",
                alignment_level="partial",
                priority_hint="medium",
                key_findings=["overall_quality:weak"],
                has_dependency_groups=True,
                has_clue_support_signal=True,
                has_shaping_gap_signal=False,
                has_authoring_audit=True,
                has_full_area_coverage=True,
                issue_categories=["clue_support_related"],
                overall_quality_status="weak",
            ),
        ],
    )
    monkeypatch.setattr(
        preset_backlog_module,
        "build_preset_alignment_audit_summary",
        lambda: synthetic_summary,
    )

    summary = build_preset_alignment_backlog_summary()
    gap_items = [item for item in summary.items if item.gap_type == "shaping_gap_unexposed"]

    assert [item.preset_id for item in gap_items] == ["preset_clue_weak_only"]
