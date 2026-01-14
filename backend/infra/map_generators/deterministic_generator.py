from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Optional, Tuple

from backend.domain.models import MapArea, MapData


@dataclass
class MapGenerationResult:
    new_areas: Dict[str, MapArea]
    new_edges: List[Tuple[str, str]]
    created_area_ids: List[str]
    warnings: List[str]
    entry_area_id: Optional[str]


class DeterministicMapGenerator:
    def generate(
        self,
        existing_map: MapData,
        parent_area_id: Optional[str],
        theme: str,
        size: int,
        seed: Optional[str],
    ) -> MapGenerationResult:
        warnings: List[str] = []
        theme_name = theme.strip() if theme and theme.strip() else "Generated"
        if theme_name == "Generated" and theme.strip() == "":
            warnings.append("theme_defaulted")
        seed_value = seed if seed is not None else "default"
        if seed is None:
            warnings.append("seed_defaulted")

        new_ids = _allocate_area_ids(existing_map, size)
        entry_id = new_ids[0] if parent_area_id is not None else None

        new_areas: Dict[str, MapArea] = {}
        for index, area_id in enumerate(new_ids, start=1):
            is_entry = entry_id == area_id
            name = (
                f"{theme_name} Entry"
                if is_entry
                else f"{theme_name} Area {index:02d}"
            )
            new_areas[area_id] = MapArea(
                id=area_id,
                name=name,
                parent_area_id=parent_area_id,
            )

        edges: List[Tuple[str, str]] = []
        for i in range(len(new_ids) - 1):
            edges.append((new_ids[i], new_ids[i + 1]))

        rng = random.Random(seed_value)
        branch_count = 0
        if size >= 4:
            branch_count = max(1, size // 3)
            branch_count = min(branch_count, size - 2)
        edges_set = set(edges)
        attempts = 0
        while len(edges_set) < len(edges) + branch_count and attempts < size * 4:
            attempts += 1
            from_index = rng.randrange(0, size - 2)
            to_index = rng.randrange(from_index + 2, size)
            edge = (new_ids[from_index], new_ids[to_index])
            if edge not in edges_set:
                edges_set.add(edge)
        edges = list(edges_set)
        edges.sort()

        existing_layer_ids = [
            area_id
            for area_id, area in existing_map.areas.items()
            if area.parent_area_id == parent_area_id
        ]
        if parent_area_id is None and existing_layer_ids:
            anchor_id = sorted(existing_layer_ids)[0]
            edges.append((anchor_id, new_ids[0]))

        if parent_area_id is not None:
            edges.append((parent_area_id, entry_id))
            if existing_layer_ids:
                anchor_id = sorted(existing_layer_ids)[0]
                edges.append((entry_id, anchor_id))

        edges.sort()

        return MapGenerationResult(
            new_areas=new_areas,
            new_edges=edges,
            created_area_ids=new_ids,
            warnings=warnings,
            entry_area_id=entry_id,
        )


def _allocate_area_ids(existing_map: MapData, size: int) -> List[str]:
    used_ids = set(existing_map.areas.keys())
    max_index = 0
    for area_id in used_ids:
        if area_id.startswith("area_"):
            suffix = area_id.replace("area_", "")
            if suffix.isdigit():
                max_index = max(max_index, int(suffix))
    new_ids: List[str] = []
    next_index = max_index + 1
    while len(new_ids) < size:
        candidate = f"area_{next_index:03d}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            new_ids.append(candidate)
        next_index += 1
    return new_ids
