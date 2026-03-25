from __future__ import annotations

from backend.domain.formal_gameplay_model import Edge, FormalGameplayModel, Goal, Node
from backend.domain.scenario_models import MaterializedScenario


def build_formal_model_from_scenario(
    scenario: MaterializedScenario,
) -> FormalGameplayModel:
    roles = scenario.roles
    nodes: list[Node] = []
    edges: list[Edge] = []

    for area_id in sorted(scenario.topology.areas.keys()):
        nodes.append(Node(id=area_id, type="area"))

    for entity_id, entity in sorted(scenario.entities.items()):
        if entity.kind == "gate":
            nodes.append(Node(id=entity_id, type="gate"))
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
    edges.append(
        Edge(
            from_id=gate_rule.gate_entity_id,
            to_id=gate_rule.to_area_id,
            type="blocks_transition",
        )
    )
    edges.append(
        Edge(
            from_id=gate_rule.gate_entity_id,
            to_id=gate_rule.required_item_id,
            type="requires",
        )
    )
    edges.append(
        Edge(
            from_id=gate_rule.required_item_id,
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

    return FormalGameplayModel(
        nodes=nodes,
        edges=edges,
        goals=goals,
        start_area_id=roles.start_area_id,
    )
