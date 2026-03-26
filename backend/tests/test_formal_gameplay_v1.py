from __future__ import annotations

from backend.app.formal_mapper import build_formal_model_from_scenario
from backend.app.formal_validator import validate_formal_model
from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params
from backend.app.scenario_validator import validate_materialized_scenario
from backend.domain.scenario_models import (
    ScenarioDependencyGroup,
    ScenarioEntity,
    ScenarioItem,
)


def _build_any_of_scenario(
    *,
    alt_clue_area_id: str | None = None,
    include_alt_clue: bool = True,
):
    scenario = build_materialized_scenario(
        normalize_scenario_params({"area_count": 5, "layout_type": "branch"})
    )
    branch_area_id = scenario.topology.branch_area_ids[0]
    alt_clue_source_id = "clue_source_alt_001"
    alt_item_id = "required_item_alt_001"

    entities_update = dict(scenario.entities)
    if include_alt_clue:
        entities_update[alt_clue_source_id] = ScenarioEntity(
            id=alt_clue_source_id,
            kind="clue_source",
            area_id=alt_clue_area_id or branch_area_id,
            reveals_item_id=alt_item_id,
        )

    any_of_scenario = scenario.model_copy(
        update={
            "entities": entities_update,
            "items": {
                **scenario.items,
                alt_item_id: ScenarioItem(
                    id=alt_item_id,
                    revealed_by_entity_id=alt_clue_source_id if include_alt_clue else "",
                    required_by_gate_entity_id=scenario.roles.gate_entity_id,
                ),
            },
            "dependency_groups": {
                scenario.gate_rule.dependency_group_id: ScenarioDependencyGroup(
                    id=scenario.gate_rule.dependency_group_id,
                    mode="any_of",
                    node_ids=(scenario.roles.required_item_id, alt_item_id),
                )
            },
        }
    )
    validate_materialized_scenario(any_of_scenario)
    return any_of_scenario, alt_clue_source_id, alt_item_id


def test_formal_validator_accepts_any_of_with_two_distinct_reachable_branches() -> None:
    scenario, alt_clue_source_id, alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)

    result = validate_formal_model(model)

    gate_nodes = [node for node in model.nodes if node.type == "gate"]
    assert len(gate_nodes) == 1
    assert gate_nodes[0].dependency_group_id == scenario.gate_rule.dependency_group_id
    assert model.dependency_groups[0].mode == "any_of"
    assert model.gate_clue_support_gaps == []
    assert any(node.id == alt_clue_source_id and node.type == "clue_source" for node in model.nodes)
    assert any(node.id == alt_item_id and node.type == "item_dependency" for node in model.nodes)
    assert result.main_path_solvable is True
    assert result.overall_quality_status == "good"
    assert len(result.gate_quality_statuses) == 1
    assert result.gate_quality_statuses[0].quality_status == "good"
    assert all(issue.code != "critical_gate_unsatisfied" for issue in result.issues)
    assert all(issue.code != "critical_item_unreachable" for issue in result.issues)
    assert all(issue.code != "multi_path_coverage_missing" for issue in result.issues)
    assert all(
        issue.code != "missing_clue_support_for_candidate"
        for issue in result.issues
    )


def test_formal_validator_warns_when_any_of_only_has_one_reachable_branch() -> None:
    scenario, alt_clue_source_id, _alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)
    broken_primary_path = model.model_copy(
        update={
            "edges": [
                edge
                for edge in model.edges
                if not (
                    edge.type == "reveals"
                    and edge.from_id == scenario.roles.clue_source_id
                    and edge.to_id == scenario.roles.required_item_id
                )
            ]
        }
    )

    result = validate_formal_model(broken_primary_path)

    gate_nodes = [node for node in broken_primary_path.nodes if node.type == "gate"]
    assert len(gate_nodes) == 1
    assert gate_nodes[0].dependency_group_id == scenario.gate_rule.dependency_group_id
    assert broken_primary_path.dependency_groups[0].mode == "any_of"
    assert any(node.id == alt_clue_source_id and node.type == "clue_source" for node in broken_primary_path.nodes)
    assert result.main_path_solvable is True
    assert result.overall_quality_status == "weak"
    assert len(result.gate_quality_statuses) == 1
    assert result.gate_quality_statuses[0].quality_status == "weak"
    assert len(result.gate_authoring_audits) == 1
    assert result.gate_authoring_audits[0].gate_id == scenario.roles.gate_entity_id
    assert result.gate_authoring_audits[0].quality_status == "weak"
    assert result.gate_authoring_audits[0].issue_categories == ["path_coverage_related"]
    assert result.gate_authoring_audits[0].issues == ["multi_path_coverage_missing"]
    assert result.gate_authoring_audits[0].has_shaping_gap is False
    assert all(issue.code != "critical_gate_unsatisfied" for issue in result.issues)
    assert all(issue.code != "critical_item_unreachable" for issue in result.issues)
    assert any(issue.code == "multi_path_coverage_missing" for issue in result.issues)


def test_formal_validator_rejects_any_of_when_all_alternatives_are_unreachable() -> None:
    scenario, _alt_clue_source_id, alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)
    broken_all_paths = model.model_copy(
        update={
            "edges": [
                edge
                for edge in model.edges
                if not (
                    edge.type == "reveals"
                    and edge.to_id in {scenario.roles.required_item_id, alt_item_id}
                )
            ]
        }
    )

    result = validate_formal_model(broken_all_paths)

    assert result.main_path_solvable is False
    assert result.overall_quality_status == "failing"
    assert len(result.gate_quality_statuses) == 1
    assert result.gate_quality_statuses[0].quality_status == "failing"
    assert len(result.gate_authoring_audits) == 1
    assert result.gate_authoring_audits[0].gate_id == scenario.roles.gate_entity_id
    assert result.gate_authoring_audits[0].quality_status == "failing"
    assert result.gate_authoring_audits[0].issue_categories == ["solvability_related"]
    assert result.gate_authoring_audits[0].issues == [
        "critical_gate_unsatisfied",
        "critical_item_unreachable",
    ]
    assert result.gate_authoring_audits[0].has_shaping_gap is False
    assert any(issue.code == "critical_gate_unsatisfied" for issue in result.issues)
    assert any(
        issue.code == "critical_item_unreachable"
        and issue.refs.get("mode") == "any_of"
        for issue in result.issues
    )
    assert result.overall_authoring_audit.overall_quality_status == "failing"
    assert result.overall_authoring_audit.gate_count_by_quality == {
        "good": 0,
        "weak": 0,
        "failing": 1,
    }
    assert result.overall_authoring_audit.issue_count_by_category == {
        "solvability_related": 1,
        "path_coverage_related": 0,
        "clue_support_related": 0,
        "shaping_gap_related": 0,
    }
    assert result.overall_authoring_audit.gates_with_shaping_gaps == []


def test_formal_validator_warns_when_any_of_candidates_share_same_support_area() -> None:
    scenario, _alt_clue_source_id, _alt_item_id = _build_any_of_scenario(
        alt_clue_area_id="area_clue"
    )
    model = build_formal_model_from_scenario(scenario)

    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert any(
        issue.code == "multi_path_coverage_missing"
        and issue.refs.get("reachable_support_area_signatures") == [["area_clue"]]
        for issue in result.issues
    )


def test_formal_validator_does_not_apply_multi_path_coverage_to_all_of_gate() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    model = build_formal_model_from_scenario(scenario)

    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert all(issue.code != "multi_path_coverage_missing" for issue in result.issues)
    assert all(
        issue.code != "missing_clue_support_for_candidate"
        for issue in result.issues
    )


def test_formal_validator_warns_when_any_of_candidate_has_no_clue_support() -> None:
    scenario, _alt_clue_source_id, alt_item_id = _build_any_of_scenario(
        include_alt_clue=False
    )
    model = build_formal_model_from_scenario(scenario)
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.overall_quality_status == "weak"
    assert len(result.gate_quality_statuses) == 1
    assert result.gate_quality_statuses[0].quality_status == "weak"
    assert len(model.gate_clue_support_gaps) == 1
    assert model.gate_clue_support_gaps[0].gate_id == scenario.roles.gate_entity_id
    assert model.gate_clue_support_gaps[0].item_id == alt_item_id
    assert model.gate_clue_support_gaps[0].source == "generator_fallback"
    assert len(result.gate_authoring_audits) == 1
    assert result.gate_authoring_audits[0].gate_id == scenario.roles.gate_entity_id
    assert result.gate_authoring_audits[0].quality_status == "weak"
    assert result.gate_authoring_audits[0].issue_categories == [
        "clue_support_related",
        "path_coverage_related",
        "shaping_gap_related",
    ]
    assert result.gate_authoring_audits[0].issues == [
        "missing_clue_support_for_candidate",
        "multi_path_coverage_missing",
    ]
    assert result.gate_authoring_audits[0].has_shaping_gap is True
    assert any(
        issue.code == "missing_clue_support_for_candidate"
        and issue.refs.get("item_id") == alt_item_id
        and issue.refs.get("support_gap_source") == "generator_fallback"
        for issue in result.issues
    )
    assert result.overall_authoring_audit.overall_quality_status == "weak"
    assert result.overall_authoring_audit.gate_count_by_quality == {
        "good": 0,
        "weak": 1,
        "failing": 0,
    }
    assert result.overall_authoring_audit.issue_count_by_category == {
        "solvability_related": 0,
        "path_coverage_related": 1,
        "clue_support_related": 1,
        "shaping_gap_related": 1,
    }
    assert result.overall_authoring_audit.gates_with_shaping_gaps == [
        scenario.roles.gate_entity_id
    ]


def test_formal_validator_warns_but_does_not_crash_when_any_of_has_no_clue_data() -> None:
    scenario, _alt_clue_source_id, alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)
    no_clue_data = model.model_copy(update={"gate_clues": []})

    result = validate_formal_model(no_clue_data)

    assert result.main_path_solvable is True
    warned_item_ids = {
        issue.refs.get("item_id")
        for issue in result.issues
        if issue.code == "missing_clue_support_for_candidate"
    }
    assert warned_item_ids == {scenario.roles.required_item_id, alt_item_id}


def test_formal_validator_reports_missing_dependency_group_item_ref() -> None:
    scenario, _alt_clue_source_id, alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)
    broken_group = model.model_copy(
        update={
            "dependency_groups": [
                model.dependency_groups[0].model_copy(
                    update={
                        "node_ids": [
                            scenario.roles.required_item_id,
                            alt_item_id,
                            "missing_item_001",
                        ]
                    }
                )
            ]
        }
    )

    result = validate_formal_model(broken_group)

    assert any(
        issue.code == "missing_structure"
        and issue.refs.get("kind") == "dependency_group_ref"
        for issue in result.issues
    )


def test_formal_validator_reports_missing_gate_dependency_group_ref() -> None:
    scenario, _alt_clue_source_id, _alt_item_id = _build_any_of_scenario()
    model = build_formal_model_from_scenario(scenario)
    broken_gate = model.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"dependency_group_id": "missing_dep_group_001"})
                if node.type == "gate"
                else node
                for node in model.nodes
            ]
        }
    )

    result = validate_formal_model(broken_gate)

    assert any(
        issue.code == "missing_structure"
        and issue.refs.get("kind") == "dependency_group"
        for issue in result.issues
    )
