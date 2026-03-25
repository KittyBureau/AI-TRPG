from __future__ import annotations

import backend.app.scenario_bridge as scenario_bridge_module
from backend.app.formal_mapper import build_formal_model_from_scenario
from backend.app.formal_validator import validate_formal_model
from backend.app.scenario_bridge import build_scenario_runtime_bridge
from backend.app.scenario_builder import build_materialized_scenario
from backend.app.scenario_templates import normalize_scenario_params
from backend.domain.formal_gameplay_model import Edge, ValidationIssue, ValidationResult


def test_formal_validator_accepts_valid_generated_scenario() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))

    model = build_formal_model_from_scenario(scenario)
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.issues == []
    assert all(node.type != "goal" for node in model.nodes)


def test_formal_validator_marks_missing_item_source_as_unsolvable() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    model = build_formal_model_from_scenario(scenario)
    broken = model.model_copy(
        update={
            "edges": [
                edge for edge in model.edges if not (
                    edge.type == "reveals" and edge.to_id == scenario.roles.required_item_id
                )
            ]
        }
    )

    result = validate_formal_model(broken)

    assert result.main_path_solvable is False
    assert any(issue.code == "critical_item_unreachable" for issue in result.issues)
    assert any(issue.code == "critical_gate_unsatisfied" for issue in result.issues)


def test_formal_validator_reports_missing_structure_for_broken_graph() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    model = build_formal_model_from_scenario(scenario)
    broken = model.model_copy(
        update={
            "edges": [
                *model.edges,
                Edge(from_id="missing_area_001", to_id=scenario.roles.start_area_id, type="transition"),
            ]
        }
    )

    result = validate_formal_model(broken)

    assert any(issue.code == "missing_structure" for issue in result.issues)


def test_formal_validator_reports_missing_goal_target() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    model = build_formal_model_from_scenario(scenario)
    broken = model.model_copy(
        update={"goals": [model.goals[0].model_copy(update={"target_id": "missing_target_001"})]}
    )

    result = validate_formal_model(broken)

    assert any(
        issue.code == "missing_structure" and issue.refs.get("kind") == "goal_target"
        for issue in result.issues
    )


def test_formal_validator_reports_missing_start_area() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    model = build_formal_model_from_scenario(scenario)
    broken = model.model_copy(update={"start_area_id": "missing_start_001"})

    result = validate_formal_model(broken)

    assert any(
        issue.code == "missing_structure" and issue.refs.get("kind") == "start_area"
        for issue in result.issues
    )


def test_bridge_attaches_read_only_formal_validation_result() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))

    bridge = build_scenario_runtime_bridge(scenario)

    assert bridge.formal_validation is not None
    assert bridge.formal_validation.main_path_solvable is True
    assert bridge.formal_validation.issues == []


def test_bridge_does_not_fail_when_formal_validation_reports_errors() -> None:
    scenario = build_materialized_scenario(normalize_scenario_params({}))
    original_validator = scenario_bridge_module.validate_formal_model
    scenario_bridge_module.validate_formal_model = lambda _model: ValidationResult(
        main_path_solvable=False,
        issues=[
            ValidationIssue(
                code="goal_unreachable",
                refs={"goal_ids": ["goal:enter_area:area_target"]},
            )
        ],
    )
    try:
        bridge = build_scenario_runtime_bridge(scenario)
    finally:
        scenario_bridge_module.validate_formal_model = original_validator

    assert bridge.formal_validation is not None
    assert bridge.formal_validation.main_path_solvable is False
    assert bridge.formal_validation.issues[0].code == "goal_unreachable"
