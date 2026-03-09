from __future__ import annotations

from typing import Any, Dict, List

from backend.domain.models import Campaign


def build_area_local_entity_views(
    campaign: Campaign,
    area_id: str | None,
) -> List[Dict[str, Any]]:
    if not isinstance(area_id, str) or not area_id.strip():
        return []

    entities_in_area: List[Dict[str, Any]] = []
    for entity in sorted(campaign.entities.values(), key=lambda item: item.id):
        if entity.loc.type != "area" or entity.loc.id != area_id:
            continue
        entities_in_area.append(
            {
                "id": entity.id,
                "kind": entity.kind,
                "label": entity.label,
                "tags": list(entity.tags),
                "verbs": list(entity.verbs),
                "state": dict(entity.state),
            }
        )
    return entities_in_area
