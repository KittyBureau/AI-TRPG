from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from backend.domain.models import MapConnection, MapData


def migrate_map_dict(map_data: Dict[str, Any]) -> None:
    areas = map_data.get("areas")
    connections = map_data.get("connections")
    if not isinstance(areas, dict) or not isinstance(connections, list):
        return

    missing_ids: List[str] = []
    for area_id, area in areas.items():
        if not isinstance(area, dict):
            continue
        if "reachable_area_ids" not in area:
            area["reachable_area_ids"] = []
            missing_ids.append(area_id)

    if not missing_ids:
        return

    missing_set = set(missing_ids)
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        from_id = connection.get("from_area_id")
        to_id = connection.get("to_area_id")
        if not isinstance(from_id, str) or not isinstance(to_id, str):
            continue
        if from_id not in missing_set:
            continue
        area = areas.get(from_id)
        if not isinstance(area, dict):
            continue
        reachable = area.get("reachable_area_ids")
        if isinstance(reachable, list):
            reachable.append(to_id)

    for area_id in missing_ids:
        area = areas.get(area_id)
        if not isinstance(area, dict):
            continue
        reachable = area.get("reachable_area_ids")
        if not isinstance(reachable, list):
            continue
        deduped = sorted(
            {value for value in reachable if isinstance(value, str)}
        )
        area["reachable_area_ids"] = deduped


def normalize_map(map_data: MapData) -> None:
    for area in map_data.areas.values():
        area.reachable_area_ids = sorted(area.reachable_area_ids)

    connections: List[MapConnection] = []
    for area_id in sorted(map_data.areas.keys()):
        area = map_data.areas[area_id]
        for target_id in area.reachable_area_ids:
            connections.append(
                MapConnection(from_area_id=area_id, to_area_id=target_id)
            )

    connections.sort(
        key=lambda connection: (connection.from_area_id, connection.to_area_id)
    )
    map_data.connections = connections


def validate_map(map_data: MapData) -> List[str]:
    errors: List[str] = []
    area_ids = set(map_data.areas.keys())

    for area_id, area in map_data.areas.items():
        reachable = area.reachable_area_ids
        if any(not isinstance(value, str) for value in reachable):
            errors.append(f"area:{area_id}:reachable_not_string")
        if len(reachable) != len(set(reachable)):
            errors.append(f"area:{area_id}:reachable_duplicate")
        if area_id in reachable:
            errors.append(f"area:{area_id}:reachable_self_loop")
        if any(target_id not in area_ids for target_id in reachable):
            errors.append(f"area:{area_id}:reachable_missing_target")

    groups: Dict[Optional[str], List[str]] = {}
    for area_id, area in map_data.areas.items():
        groups.setdefault(area.parent_area_id, []).append(area_id)

    for parent_id, nodes in groups.items():
        if len(nodes) <= 1:
            continue
        adjacency: Dict[str, Set[str]] = {node: set() for node in nodes}
        for node in nodes:
            for target_id in map_data.areas[node].reachable_area_ids:
                if target_id in adjacency:
                    adjacency[node].add(target_id)
                    adjacency[target_id].add(node)
        visited: Set[str] = set()
        stack = [nodes[0]]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency[current] - visited)
        if len(visited) != len(nodes):
            errors.append(f"parent:{parent_id}:disconnected")

    return errors


def require_valid_map(map_data: MapData) -> None:
    errors = validate_map(map_data)
    if errors:
        raise ValueError("invalid_map:" + ",".join(errors))
