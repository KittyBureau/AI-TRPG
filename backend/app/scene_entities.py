from __future__ import annotations

from typing import Any, Dict, List

from backend.app.item_operations import build_area_root_stack_views
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


def build_area_map_entity_views(
    campaign: Campaign,
    area_id: str | None,
) -> List[Dict[str, Any]]:
    if not isinstance(area_id, str) or not area_id.strip():
        return []

    views = build_area_local_entity_views(campaign, area_id)
    existing_ids = {entry["id"] for entry in views if isinstance(entry.get("id"), str)}

    for stack_view in build_area_root_stack_views(campaign, area_id):
        stack_id = stack_view.get("id")
        if not isinstance(stack_id, str) or not stack_id.strip() or stack_id in existing_ids:
            continue

        state: Dict[str, Any] = {
            "quantity": stack_view.get("quantity", 1),
            "item_id": stack_view.get("item_id"),
        }
        if stack_view.get("is_container"):
            state["opened"] = bool(stack_view.get("opened"))
        if "contents" in stack_view:
            state["contents"] = stack_view["contents"]

        views.append(
            {
                "id": stack_id,
                "kind": "container" if stack_view.get("is_container") else "item",
                "label": stack_view.get("label", stack_id),
                "tags": list(stack_view.get("tags", [])),
                "verbs": list(stack_view.get("verbs", [])),
                "state": state,
            }
        )
        existing_ids.add(stack_id)

    return views
