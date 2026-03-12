from __future__ import annotations

from backend.app.scenario_validator import validate_materialized_scenario
from backend.domain.scenario_bridge_models import (
    ScenarioBridgeArea,
    ScenarioBridgeCompletion,
    ScenarioBridgeGate,
    ScenarioBridgeInteractable,
    ScenarioBridgeKeyItem,
    ScenarioRuntimeBridge,
)
from backend.domain.scenario_models import MaterializedScenario


def build_scenario_runtime_bridge(
    scenario: MaterializedScenario,
) -> ScenarioRuntimeBridge:
    validate_materialized_scenario(scenario)

    if scenario.template_id != "key_gate_scenario":
        raise ValueError(f"unsupported bridge template: {scenario.template_id}")

    roles = scenario.roles
    areas = {
        area_id: ScenarioBridgeArea(
            id=area.id,
            kind=area.kind,
            reachable_area_ids=area.connected_area_ids,
        )
        for area_id, area in scenario.topology.areas.items()
    }
    interactables = {
        roles.hint_source_id: ScenarioBridgeInteractable(
            id=roles.hint_source_id,
            kind="hint_source",
            area_id=roles.start_area_id,
        ),
        roles.clue_source_id: ScenarioBridgeInteractable(
            id=roles.clue_source_id,
            kind="searchable_clue_source",
            area_id=roles.clue_area_id,
            grants_item_id=roles.required_item_id,
        ),
        roles.gate_entity_id: ScenarioBridgeInteractable(
            id=roles.gate_entity_id,
            kind="gate",
            area_id=roles.gate_area_id,
            requires_item_id=roles.required_item_id,
            leads_to_area_id=roles.target_area_id,
        ),
    }

    return ScenarioRuntimeBridge(
        template_id=scenario.template_id,
        template_version=scenario.template_version,
        layout_type=scenario.params.layout_type,
        difficulty=scenario.params.difficulty,
        area_count=scenario.params.area_count,
        start_area_id=roles.start_area_id,
        clue_area_id=roles.clue_area_id,
        target_area_id=roles.target_area_id,
        areas=areas,
        interactables=interactables,
        key_item=ScenarioBridgeKeyItem(
            item_id=roles.required_item_id,
            source_interactable_id=roles.clue_source_id,
        ),
        gate=ScenarioBridgeGate(
            from_area_id=roles.gate_area_id,
            to_area_id=roles.target_area_id,
            interactable_id=roles.gate_entity_id,
            required_item_id=roles.required_item_id,
        ),
        completion=ScenarioBridgeCompletion(
            type="enter_area",
            target_area_id=roles.target_area_id,
        ),
    )
