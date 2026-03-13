from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.item_runtime import (
    resolve_stack_root,
    validate_and_sync_campaign_items,
)
from backend.domain.models import Campaign, Entity, RuntimeItemStack

DEFAULT_CARRY_MASS_LIMIT = 60.0
DEFAULT_ENTITY_MASS = 1.0
DEFAULT_STACK_MASS = 1.0
PORTABLE_ENTITY_KINDS = {"item", "object", "container"}


def get_stack_or_none(
    campaign: Campaign,
    stack_id: str,
) -> Optional[RuntimeItemStack]:
    if not isinstance(stack_id, str):
        return None
    normalized_stack_id = stack_id.strip()
    if not normalized_stack_id:
        return None
    stack = campaign.items.get(normalized_stack_id)
    if stack is None:
        return None
    if not isinstance(stack.quantity, int) or stack.quantity <= 0:
        return None
    return stack


def list_area_root_stacks(
    campaign: Campaign,
    area_id: str | None,
) -> List[RuntimeItemStack]:
    if not isinstance(area_id, str) or not area_id.strip():
        return []
    normalized_area_id = area_id.strip()
    stacks: List[RuntimeItemStack] = []
    for stack_id in sorted(campaign.items.keys()):
        stack = get_stack_or_none(campaign, stack_id)
        if stack is None:
            continue
        if stack.parent_type != "area" or stack.parent_id != normalized_area_id:
            continue
        stacks.append(stack)
    return stacks


def build_area_root_stack_views(
    campaign: Campaign,
    area_id: str | None,
) -> List[Dict[str, Any]]:
    views: List[Dict[str, Any]] = []
    for stack in list_area_root_stacks(campaign, area_id):
        views.append(
            {
                "id": stack.stack_id,
                "item_id": stack.definition_id,
                "label": stack.label,
                "quantity": stack.quantity,
                "tags": list(stack.tags),
                "verbs": ["take"],
                "is_container": bool(stack.is_container),
            }
        )
    return views


def is_stack_reachable(
    campaign: Campaign,
    stack_id: str,
    *,
    actor_id: str,
    current_area_id: str | None,
) -> bool:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        return False
    try:
        root_type, root_id = resolve_stack_root(campaign, stack_id)
    except ValueError:
        return False
    if root_type == "actor":
        return root_id == actor_id
    if root_type == "area":
        return isinstance(current_area_id, str) and root_id == current_area_id
    return False


def is_area_root_stack_visible(
    campaign: Campaign,
    stack_id: str,
    *,
    area_id: str | None,
) -> bool:
    stack = get_stack_or_none(campaign, stack_id)
    return (
        stack is not None
        and isinstance(area_id, str)
        and stack.parent_type == "area"
        and stack.parent_id == area_id
    )


def is_direct_actor_stack(
    campaign: Campaign,
    stack_id: str,
    *,
    actor_id: str,
) -> bool:
    stack = get_stack_or_none(campaign, stack_id)
    return (
        stack is not None
        and stack.parent_type == "actor"
        and stack.parent_id == actor_id
    )


def transfer_stack_parent(
    campaign: Campaign,
    *,
    stack_id: str,
    parent_type: str,
    parent_id: str,
) -> RuntimeItemStack:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    stack.parent_type = parent_type  # type: ignore[assignment]
    stack.parent_id = parent_id
    validate_and_sync_campaign_items(campaign)
    return stack


def compute_entity_mass(entity: Entity) -> float:
    raw_mass = entity.props.get("mass")
    if isinstance(raw_mass, (int, float)) and raw_mass > 0:
        return float(raw_mass)
    return DEFAULT_ENTITY_MASS


def compute_stack_mass(stack: RuntimeItemStack) -> float:
    raw_mass = stack.props.get("mass")
    unit_mass = float(raw_mass) if isinstance(raw_mass, (int, float)) and raw_mass > 0 else DEFAULT_STACK_MASS
    return unit_mass * stack.quantity


def compute_actor_item_mass(
    campaign: Campaign,
    actor_id: str,
) -> float:
    total = 0.0

    for stack_id in sorted(campaign.items.keys()):
        stack = get_stack_or_none(campaign, stack_id)
        if stack is None:
            continue
        try:
            root_type, root_id = resolve_stack_root(campaign, stack_id)
        except ValueError:
            continue
        if root_type != "actor" or root_id != actor_id:
            continue
        total += compute_stack_mass(stack)

    for entity in campaign.entities.values():
        if entity.loc.type != "actor" or entity.loc.id != actor_id:
            continue
        if entity.kind not in PORTABLE_ENTITY_KINDS:
            continue
        total += compute_entity_mass(entity)

    return total


def carry_mass_limit(
    campaign: Campaign,
    actor_id: str,
) -> float:
    actor = campaign.actors.get(actor_id)
    if actor is None or not isinstance(actor.meta, dict):
        return DEFAULT_CARRY_MASS_LIMIT
    raw_limit = actor.meta.get("carry_mass_limit")
    if isinstance(raw_limit, (int, float)) and raw_limit > 0:
        return float(raw_limit)
    return DEFAULT_CARRY_MASS_LIMIT


def would_exceed_actor_carry_limit(
    campaign: Campaign,
    actor_id: str,
    *,
    additional_mass: float,
) -> bool:
    normalized_additional_mass = (
        float(additional_mass) if isinstance(additional_mass, (int, float)) and additional_mass > 0 else 0.0
    )
    current_mass = compute_actor_item_mass(campaign, actor_id)
    return current_mass + normalized_additional_mass > carry_mass_limit(campaign, actor_id)


__all__ = [
    "build_area_root_stack_views",
    "carry_mass_limit",
    "compute_actor_item_mass",
    "compute_entity_mass",
    "compute_stack_mass",
    "get_stack_or_none",
    "is_area_root_stack_visible",
    "is_direct_actor_stack",
    "is_stack_reachable",
    "list_area_root_stacks",
    "transfer_stack_parent",
    "would_exceed_actor_carry_limit",
]
