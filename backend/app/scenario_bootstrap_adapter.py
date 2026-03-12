from __future__ import annotations

from backend.domain.scenario_bootstrap_models import (
    ScenarioBootstrapArea,
    ScenarioBootstrapCompletion,
    ScenarioBootstrapFragment,
    ScenarioBootstrapGate,
    ScenarioBootstrapHintSource,
    ScenarioBootstrapKeyItemGrant,
    ScenarioBootstrapSearchableClueSource,
)
from backend.domain.scenario_bridge_models import ScenarioRuntimeBridge


def build_scenario_bootstrap_fragment(
    bridge: ScenarioRuntimeBridge,
) -> ScenarioBootstrapFragment:
    _validate_bridge_for_bootstrap(bridge)

    clue_source = bridge.interactables[bridge.key_item.source_interactable_id]
    gate_interactable = bridge.interactables[bridge.gate.interactable_id]
    hint_interactable = _find_hint_source(bridge)

    return ScenarioBootstrapFragment(
        template_id=bridge.template_id,
        template_version=bridge.template_version,
        layout_type=bridge.layout_type,
        difficulty=bridge.difficulty,
        area_count=bridge.area_count,
        start_area_id=bridge.start_area_id,
        clue_area_id=bridge.clue_area_id,
        target_area_id=bridge.target_area_id,
        areas={
            area_id: ScenarioBootstrapArea(
                id=area.id,
                kind=area.kind,
                reachable_area_ids=area.reachable_area_ids,
            )
            for area_id, area in bridge.areas.items()
        },
        hint_source=ScenarioBootstrapHintSource(
            interactable_id=hint_interactable.id,
            area_id=hint_interactable.area_id,
        ),
        searchable_clue_source=ScenarioBootstrapSearchableClueSource(
            interactable_id=clue_source.id,
            area_id=clue_source.area_id,
        ),
        key_item_grant=ScenarioBootstrapKeyItemGrant(
            item_id=bridge.key_item.item_id,
            source_interactable_id=bridge.key_item.source_interactable_id,
            source_area_id=clue_source.area_id,
        ),
        gate=ScenarioBootstrapGate(
            interactable_id=gate_interactable.id,
            area_id=gate_interactable.area_id,
            from_area_id=bridge.gate.from_area_id,
            to_area_id=bridge.gate.to_area_id,
            required_item_id=bridge.gate.required_item_id,
        ),
        completion=ScenarioBootstrapCompletion(
            type=bridge.completion.type,
            target_area_id=bridge.completion.target_area_id,
        ),
    )


def _validate_bridge_for_bootstrap(bridge: ScenarioRuntimeBridge) -> None:
    if bridge.template_id != "key_gate_scenario":
        raise ValueError(f"unsupported bootstrap fragment template: {bridge.template_id}")
    if len(bridge.areas) != bridge.area_count:
        raise ValueError("bridge area_count does not match area map size")
    if bridge.start_area_id not in bridge.areas:
        raise ValueError("bridge start area is missing")
    if bridge.clue_area_id not in bridge.areas:
        raise ValueError("bridge clue area is missing")
    if bridge.target_area_id not in bridge.areas:
        raise ValueError("bridge target area is missing")
    if bridge.areas[bridge.start_area_id].kind != "start":
        raise ValueError("bridge start area semantics are invalid")
    if bridge.areas[bridge.clue_area_id].kind != "clue":
        raise ValueError("bridge clue area semantics are invalid")
    if bridge.areas[bridge.target_area_id].kind != "target":
        raise ValueError("bridge target area semantics are invalid")
    if bridge.key_item.source_interactable_id not in bridge.interactables:
        raise ValueError("bridge key item source interactable is missing")
    if bridge.gate.interactable_id not in bridge.interactables:
        raise ValueError("bridge gate interactable is missing")
    if bridge.gate.from_area_id not in bridge.areas or bridge.gate.to_area_id not in bridge.areas:
        raise ValueError("bridge gate areas are missing")
    if bridge.completion.type != "enter_area":
        raise ValueError("bridge completion semantics must be target-entry based")
    if bridge.completion.target_area_id != bridge.target_area_id:
        raise ValueError("bridge completion target must match bridge target area")

    clue_source = bridge.interactables[bridge.key_item.source_interactable_id]
    if clue_source.kind != "searchable_clue_source":
        raise ValueError("bridge key item source must be a searchable clue source")
    if clue_source.area_id != bridge.clue_area_id:
        raise ValueError("bridge searchable clue source must live in the clue area")
    if clue_source.grants_item_id != bridge.key_item.item_id:
        raise ValueError("bridge searchable clue source must grant the bridge key item")

    gate = bridge.interactables[bridge.gate.interactable_id]
    if gate.kind != "gate":
        raise ValueError("bridge gate interactable semantics are invalid")
    if gate.area_id != bridge.gate.from_area_id:
        raise ValueError("bridge gate interactable must live in the gate area")
    if gate.requires_item_id != bridge.gate.required_item_id:
        raise ValueError("bridge gate interactable must require the bridge key item")
    if gate.leads_to_area_id != bridge.gate.to_area_id:
        raise ValueError("bridge gate interactable must lead to the gate target area")

    _find_hint_source(bridge)


def _find_hint_source(bridge: ScenarioRuntimeBridge):
    hint_sources = [
        interactable
        for interactable in bridge.interactables.values()
        if interactable.kind == "hint_source"
    ]
    if len(hint_sources) != 1:
        raise ValueError("bridge must contain exactly one hint source")
    hint_source = hint_sources[0]
    if hint_source.area_id != bridge.start_area_id:
        raise ValueError("bridge hint source must live in the start area")
    return hint_source
