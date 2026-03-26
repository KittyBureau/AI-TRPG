from __future__ import annotations

from backend.domain.formal_gameplay_model import (
    DependencyGroup,
    Edge,
    FormalGameplayModel,
    GateClue,
    GateClueSupportGap,
    Goal,
    Node,
)
from backend.domain.scenario_models import MaterializedScenario


def build_formal_model_from_scenario(
    scenario: MaterializedScenario,
) -> FormalGameplayModel:
    roles = scenario.roles
    nodes: list[Node] = []
    edges: list[Edge] = []
    dependency_groups: list[DependencyGroup] = []
    gate_clues: list[GateClue] = []
    gate_clue_support_gaps: list[GateClueSupportGap] = []

    for area_id in sorted(scenario.topology.areas.keys()):
        nodes.append(Node(id=area_id, type="area"))

    gate_dependency_group_id = scenario.gate_rule.dependency_group_id or None
    for entity_id, entity in sorted(scenario.entities.items()):
        if entity.kind == "gate":
            nodes.append(
                Node(
                    id=entity_id,
                    type="gate",
                    dependency_group_id=gate_dependency_group_id,
                )
            )
            edges.append(Edge(from_id=entity_id, to_id=entity.area_id, type="located_in"))
        elif entity.kind == "clue_source":
            nodes.append(Node(id=entity_id, type="clue_source"))
            edges.append(Edge(from_id=entity_id, to_id=entity.area_id, type="located_in"))

    for item_id in sorted(scenario.items.keys()):
        nodes.append(Node(id=item_id, type="item_dependency"))

    goal_id = f"goal:{scenario.goal_rule.type}:{scenario.goal_rule.target_area_id}"
    goals = [
        Goal(
            id=goal_id,
            type="enter_area",
            target_id=scenario.goal_rule.target_area_id,
        )
    ]

    seen_transitions: set[tuple[str, str]] = set()
    for area_id, area in sorted(scenario.topology.areas.items()):
        for neighbor_id in sorted(area.connected_area_ids):
            signature = (area_id, neighbor_id)
            if signature in seen_transitions:
                continue
            seen_transitions.add(signature)
            edges.append(
                Edge(from_id=area_id, to_id=neighbor_id, type="transition")
            )

    gate_rule = scenario.gate_rule
    dependency_item_ids: list[str]
    if gate_rule.dependency_group_id:
        scenario_group = scenario.dependency_groups.get(gate_rule.dependency_group_id)
        if scenario_group is not None:
            dependency_groups.append(
                DependencyGroup(
                    id=scenario_group.id,
                    mode=scenario_group.mode,
                    node_ids=list(scenario_group.node_ids),
                )
            )
            dependency_item_ids = list(scenario_group.node_ids)
        else:
            dependency_item_ids = [gate_rule.required_item_id]
    else:
        dependency_groups.append(
            DependencyGroup(
                id=f"dep_group:{gate_rule.gate_entity_id}",
                mode="all_of",
                node_ids=[gate_rule.required_item_id],
            )
        )
        dependency_item_ids = [gate_rule.required_item_id]
        for node in nodes:
            if node.id == gate_rule.gate_entity_id and node.type == "gate":
                node.dependency_group_id = dependency_groups[0].id
                break

    edges.append(
        Edge(
            from_id=gate_rule.gate_entity_id,
            to_id=gate_rule.to_area_id,
            type="blocks_transition",
        )
    )
    for dependency_item_id in dependency_item_ids:
        edges.append(
            Edge(
                from_id=gate_rule.gate_entity_id,
                to_id=dependency_item_id,
                type="requires",
            )
        )
        edges.append(
            Edge(
                from_id=dependency_item_id,
                to_id=gate_rule.gate_entity_id,
                type="satisfies",
            )
        )

    for entity_id, entity in sorted(scenario.entities.items()):
        if entity.kind != "clue_source" or not entity.reveals_item_id:
            continue
        edges.append(
            Edge(from_id=entity_id, to_id=entity.reveals_item_id, type="reveals")
        )

    gate_clue_items: dict[tuple[str, str], list[str]] = {}
    for item_id, item in sorted(scenario.items.items()):
        if not item.required_by_gate_entity_id:
            continue
        clue_entity = scenario.entities.get(item.revealed_by_entity_id)
        if clue_entity is not None and clue_entity.kind == "clue_source":
            signature = (item.revealed_by_entity_id, item.required_by_gate_entity_id)
            gate_clue_items.setdefault(signature, []).append(item_id)

    for (clue_id, gate_id), supported_items in sorted(gate_clue_items.items()):
        gate_clues.append(
            GateClue(
                clue_id=clue_id,
                gate_id=gate_id,
                supported_items=sorted(set(supported_items)),
                clue_type="critical",
            )
        )

    if dependency_groups and dependency_groups[0].mode == "any_of":
        supported_item_ids = {
            item_id for gate_clue in gate_clues for item_id in gate_clue.supported_items
        }
        for item_id in dependency_item_ids:
            if item_id in supported_item_ids:
                continue
            gate_clue_support_gaps.append(
                GateClueSupportGap(
                    gate_id=gate_rule.gate_entity_id,
                    item_id=item_id,
                )
            )

    return FormalGameplayModel(
        nodes=nodes,
        edges=edges,
        dependency_groups=dependency_groups,
        gate_clues=gate_clues,
        gate_clue_support_gaps=gate_clue_support_gaps,
        goals=goals,
        start_area_id=roles.start_area_id,
    )
