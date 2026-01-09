import json
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORLD_PATH = (
    REPO_ROOT / "backend" / "storage" / "worlds" / "sample_world.json"
)
DEFAULT_STATE_PATH = (
    REPO_ROOT / "backend" / "storage" / "runs" / "sample_world_state.json"
)

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
RISK_LEVELS = ["low", "medium", "high"]


class WorldMovementError(Exception):
    pass


class WorldDataError(WorldMovementError):
    pass


class EntityNotFoundError(WorldMovementError):
    pass


class InvalidPathError(WorldMovementError):
    pass


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise WorldDataError(f"File not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorldDataError(f"Invalid JSON in {path}") from exc


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")


def _risk_rank(value: str) -> int:
    if value not in RISK_ORDER:
        raise WorldDataError(f"Unknown risk level: {value}")
    return RISK_ORDER[value]


def _risk_name(rank: int) -> str:
    if 0 <= rank < len(RISK_LEVELS):
        return RISK_LEVELS[rank]
    raise WorldDataError(f"Invalid risk rank: {rank}")


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorldDataError(f"Field '{field}' must be an integer.")
    return value


def _edge_key(edge: Dict[str, Any]) -> str:
    return f"{edge['from']}->{edge['to']}"


def _sort_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(edge: Dict[str, Any]) -> tuple:
        risk_rank = _risk_rank(edge.get("risk", "low"))
        requires = edge.get("requires", [])
        if not isinstance(requires, list) or not all(
            isinstance(item, str) for item in requires
        ):
            raise WorldDataError("Edge requires must be a list of strings.")
        return (
            edge.get("from", ""),
            edge.get("to", ""),
            edge.get("type", ""),
            int(edge.get("time", 0)),
            risk_rank,
            ",".join(requires),
        )

    return sorted(edges, key=sort_key)


def _load_world(world_path: Path) -> Dict[str, Any]:
    data = _load_json(world_path)
    if not isinstance(data, dict):
        raise WorldDataError("World data must be a JSON object.")

    locations = data.get("locations")
    edges = data.get("edges")
    if not isinstance(locations, list):
        raise WorldDataError("World locations must be a list.")
    if not isinstance(edges, list):
        raise WorldDataError("World edges must be a list.")

    location_ids = []
    for location in locations:
        if not isinstance(location, dict) or "id" not in location:
            raise WorldDataError("Each location must include an id.")
        location_ids.append(location["id"])
    location_set = set(location_ids)

    for edge in edges:
        if not isinstance(edge, dict):
            raise WorldDataError("Each edge must be an object.")
        if edge.get("from") not in location_set:
            raise WorldDataError(f"Edge from unknown location: {edge.get('from')}")
        if edge.get("to") not in location_set:
            raise WorldDataError(f"Edge to unknown location: {edge.get('to')}")
        _require_int(edge.get("time"), "time")
        _risk_rank(edge.get("risk", "low"))

    return {"locations": locations, "edges": _sort_edges(edges)}


def _load_state(state_path: Path) -> Dict[str, Any]:
    data = _load_json(state_path)
    if not isinstance(data, dict):
        raise WorldDataError("World state must be a JSON object.")

    entities = data.get("entities")
    if not isinstance(entities, list):
        raise WorldDataError("World state entities must be a list.")

    data.setdefault("blocked_edges", [])
    data.setdefault("facts", [])
    data.setdefault("time", 0)

    if not isinstance(data["blocked_edges"], list):
        raise WorldDataError("blocked_edges must be a list.")
    if not isinstance(data["facts"], list):
        raise WorldDataError("facts must be a list.")
    _require_int(data["time"], "time")

    return data


def _get_entity(state: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    for entity in state.get("entities", []):
        if entity.get("id") == entity_id:
            return entity
    raise EntityNotFoundError(f"Entity not found: {entity_id}")


def _build_adjacency(edges: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    adjacency: Dict[str, List[Dict[str, Any]]] = {}
    for edge in edges:
        adjacency.setdefault(edge["from"], []).append(edge)
    for from_id in adjacency:
        adjacency[from_id] = _sort_edges(adjacency[from_id])
    return adjacency


def _path_id(nodes: List[str]) -> str:
    return "->".join(nodes)


def _parse_path_id(path_id: str) -> List[str]:
    nodes = [node for node in path_id.split("->") if node]
    if len(nodes) < 2:
        raise InvalidPathError("path_id must include at least two nodes.")
    if len(nodes) != len(set(nodes)):
        raise InvalidPathError("path_id cannot repeat nodes.")
    return nodes


def _requires_satisfied(edge: Dict[str, Any], flags: List[str]) -> bool:
    requires = edge.get("requires", [])
    if not requires:
        return True
    if not isinstance(requires, list) or not all(
        isinstance(item, str) for item in requires
    ):
        raise WorldDataError("Edge requires must be a list of strings.")
    return set(requires).issubset(set(flags))


def get_movement_paths(
    entity_id: str,
    max_depth: int = 3,
    max_paths: int = 20,
    risk_ceiling: str = "medium",
    world_path: str | Path | None = None,
    state_path: str | Path | None = None,
) -> Dict[str, Any]:
    if max_depth < 1:
        raise WorldDataError("max_depth must be >= 1.")
    if max_paths < 1:
        raise WorldDataError("max_paths must be >= 1.")

    ceiling = risk_ceiling or "high"
    ceiling_rank = _risk_rank(ceiling)

    world = _load_world(Path(world_path) if world_path else DEFAULT_WORLD_PATH)
    state = _load_state(Path(state_path) if state_path else DEFAULT_STATE_PATH)

    entity = _get_entity(state, entity_id)
    start = entity.get("location_id")
    if not isinstance(start, str) or not start:
        raise WorldDataError("Entity location_id must be a string.")

    flags = entity.get("flags", [])
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise WorldDataError("Entity flags must be a list of strings.")

    blocked = set(state.get("blocked_edges", []))
    adjacency = _build_adjacency(world["edges"])

    paths: List[Dict[str, Any]] = []

    def walk(current: str, nodes: List[str], total_time: int, max_risk: int) -> None:
        depth = len(nodes) - 1
        if depth >= max_depth:
            return
        for edge in adjacency.get(current, []):
            if _edge_key(edge) in blocked:
                continue
            if not _requires_satisfied(edge, flags):
                continue
            destination = edge["to"]
            if destination in nodes:
                continue
            edge_risk = _risk_rank(edge.get("risk", "low"))
            path_max_risk = max(max_risk, edge_risk)
            if path_max_risk > ceiling_rank:
                continue
            path_nodes = nodes + [destination]
            path_total_time = total_time + edge["time"]
            path_id = _path_id(path_nodes)
            paths.append(
                {
                    "path_id": path_id,
                    "to_location_id": destination,
                    "nodes": path_nodes,
                    "total_time": path_total_time,
                    "max_risk": _risk_name(path_max_risk),
                }
            )
            walk(destination, path_nodes, path_total_time, path_max_risk)

    walk(start, [start], 0, -1)

    def sort_key(item: Dict[str, Any]) -> tuple:
        return (
            item["total_time"],
            _risk_rank(item["max_risk"]),
            len(item["nodes"]) - 1,
            item["path_id"],
        )

    sorted_paths = sorted(paths, key=sort_key)[:max_paths]
    return {"from_location_id": start, "paths": sorted_paths}


def apply_move(
    entity_id: str,
    path_id: str,
    world_path: str | Path | None = None,
    state_path: str | Path | None = None,
) -> Dict[str, Any]:
    world = _load_world(Path(world_path) if world_path else DEFAULT_WORLD_PATH)
    state = _load_state(Path(state_path) if state_path else DEFAULT_STATE_PATH)

    entity = _get_entity(state, entity_id)
    start = entity.get("location_id")
    if not isinstance(start, str) or not start:
        raise WorldDataError("Entity location_id must be a string.")

    nodes = _parse_path_id(path_id)
    if nodes[0] != start:
        raise InvalidPathError("path_id does not start at the entity location.")

    flags = entity.get("flags", [])
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise WorldDataError("Entity flags must be a list of strings.")

    blocked = set(state.get("blocked_edges", []))
    adjacency = _build_adjacency(world["edges"])

    total_time = 0
    max_risk = -1

    for index in range(len(nodes) - 1):
        from_id = nodes[index]
        to_id = nodes[index + 1]
        candidates = [
            edge for edge in adjacency.get(from_id, []) if edge.get("to") == to_id
        ]
        if not candidates:
            raise InvalidPathError(f"No edge from {from_id} to {to_id}.")
        if len(candidates) > 1:
            raise InvalidPathError(f"Ambiguous edge from {from_id} to {to_id}.")
        edge = candidates[0]
        if _edge_key(edge) in blocked:
            raise InvalidPathError(f"Edge blocked: {_edge_key(edge)}")
        if not _requires_satisfied(edge, flags):
            raise InvalidPathError(f"Edge requires missing flags: {_edge_key(edge)}")
        edge_risk = _risk_rank(edge.get("risk", "low"))
        max_risk = max(max_risk, edge_risk)
        total_time += edge["time"]

    entity["location_id"] = nodes[-1]
    state["time"] = _require_int(state.get("time"), "time") + total_time

    facts = state.get("facts", [])
    facts.append(
        {
            "type": "move",
            "time": state["time"],
            "entity_id": entity_id,
            "from": nodes[0],
            "to": nodes[-1],
            "path_id": path_id,
        }
    )
    state["facts"] = facts

    _save_json(Path(state_path) if state_path else DEFAULT_STATE_PATH, state)

    return {
        "status": "OK",
        "entity_id": entity_id,
        "from_location_id": nodes[0],
        "to_location_id": nodes[-1],
        "path_id": path_id,
        "total_time": total_time,
        "max_risk": _risk_name(max_risk),
        "time": state["time"],
    }
