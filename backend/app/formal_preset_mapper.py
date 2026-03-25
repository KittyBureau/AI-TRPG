from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.formal_gameplay_model import Edge, FormalGameplayModel, Goal, Node

if TYPE_CHECKING:
    from backend.app.world_presets import CampaignWorldPreset


_WATCHTOWER_WORLD_ID = "test_watchtower_world"
_MIDNIGHT_ARCHIVE_WORLD_ID = "midnight_archive_world"
_MIDNIGHT_ARCHIVE_GOAL_TARGET_ID = "forged_file_shelf"
_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID = "midnight_archive_service_gate"


def build_formal_model_from_preset(
    world_id: str,
    preset: "CampaignWorldPreset",
) -> FormalGameplayModel | None:
    normalized_world_id = world_id.strip()
    if normalized_world_id == _WATCHTOWER_WORLD_ID:
        return _build_watchtower_model(preset)
    if normalized_world_id == _MIDNIGHT_ARCHIVE_WORLD_ID:
        return _build_midnight_archive_model(preset)
    return None


def _build_watchtower_model(preset: "CampaignWorldPreset") -> FormalGameplayModel:
    required_area_ids = {
        "village_gate",
        "village_square",
        "old_hut",
        "forest_path",
        "watchtower_entrance",
        "watchtower_inside",
    }
    _require_areas(preset, required_area_ids)
    _require_entity(preset, "old_hut_clue")
    _require_entity(preset, "watchtower_door")

    nodes = [Node(id=area_id, type="area") for area_id in sorted(required_area_ids)]
    nodes.extend(
        [
            Node(id="old_hut_clue", type="clue_source"),
            Node(id="watchtower_door", type="gate"),
            Node(id="tower_key", type="item_dependency"),
        ]
    )

    edges = _build_transition_edges(preset, allowed_area_ids=required_area_ids)
    edges.extend(
        [
            Edge(from_id="old_hut_clue", to_id="old_hut", type="located_in"),
            Edge(
                from_id="watchtower_door",
                to_id="watchtower_entrance",
                type="located_in",
            ),
            Edge(from_id="old_hut_clue", to_id="tower_key", type="reveals"),
            Edge(from_id="watchtower_door", to_id="tower_key", type="requires"),
            Edge(from_id="tower_key", to_id="watchtower_door", type="satisfies"),
            Edge(
                from_id="watchtower_door",
                to_id="watchtower_inside",
                type="blocks_transition",
            ),
        ]
    )

    return FormalGameplayModel(
        nodes=nodes,
        edges=edges,
        goals=[
            Goal(
                id="goal:enter_area:watchtower_inside",
                type="enter_area",
                target_id="watchtower_inside",
            )
        ],
        start_area_id="village_gate",
    )


def _build_midnight_archive_model(preset: "CampaignWorldPreset") -> FormalGameplayModel:
    # v0 preset mapping keeps only the minimal service-route critical path here.
    required_area_ids = {
        "street_gate",
        "lobby",
        "reading_room",
        "returns_annex",
        "restricted_archive",
    }
    _require_areas(preset, required_area_ids)
    _require_entity(preset, "returns_cart")
    _require_entity(preset, _MIDNIGHT_ARCHIVE_GOAL_TARGET_ID)

    nodes = [Node(id=area_id, type="area") for area_id in sorted(required_area_ids)]
    nodes.extend(
        [
            Node(id="returns_cart", type="clue_source"),
            Node(id=_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID, type="gate"),
            Node(id="routing_slip", type="item_dependency"),
            Node(id=_MIDNIGHT_ARCHIVE_GOAL_TARGET_ID, type="goal"),
        ]
    )

    edges = _build_transition_edges(preset, allowed_area_ids=required_area_ids)
    edges.extend(
        [
            Edge(from_id="returns_cart", to_id="reading_room", type="located_in"),
            Edge(
                from_id=_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID,
                to_id="returns_annex",
                type="located_in",
            ),
            Edge(
                from_id=_MIDNIGHT_ARCHIVE_GOAL_TARGET_ID,
                to_id="restricted_archive",
                type="located_in",
            ),
            Edge(from_id="returns_cart", to_id="routing_slip", type="reveals"),
            Edge(
                from_id=_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID,
                to_id="routing_slip",
                type="requires",
            ),
            Edge(
                from_id="routing_slip",
                to_id=_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID,
                type="satisfies",
            ),
            Edge(
                from_id=_MIDNIGHT_ARCHIVE_SERVICE_GATE_ID,
                to_id="restricted_archive",
                type="blocks_transition",
            ),
        ]
    )

    return FormalGameplayModel(
        nodes=nodes,
        edges=edges,
        goals=[
            Goal(
                id="goal:interact_entity:forged_file_shelf",
                type="interact_entity",
                target_id=_MIDNIGHT_ARCHIVE_GOAL_TARGET_ID,
            )
        ],
        start_area_id="street_gate",
    )


def _build_transition_edges(
    preset: "CampaignWorldPreset",
    *,
    allowed_area_ids: set[str],
) -> list[Edge]:
    edges: list[Edge] = []
    for area_id in sorted(allowed_area_ids):
        area = preset.map_data.areas[area_id]
        for neighbor_id in sorted(area.reachable_area_ids):
            if neighbor_id not in allowed_area_ids:
                continue
            edges.append(Edge(from_id=area_id, to_id=neighbor_id, type="transition"))
    return edges


def _require_areas(preset: "CampaignWorldPreset", area_ids: set[str]) -> None:
    missing = sorted(area_id for area_id in area_ids if area_id not in preset.map_data.areas)
    if missing:
        raise ValueError(f"preset missing required areas: {', '.join(missing)}")


def _require_entity(preset: "CampaignWorldPreset", entity_id: str) -> None:
    if entity_id not in preset.entities:
        raise ValueError(f"preset missing required entity: {entity_id}")
