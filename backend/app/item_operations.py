from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.item_runtime import (
    create_runtime_item_stack,
    resolve_stack_root,
    resolve_selected_stack,
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
        view = {
            "id": stack.stack_id,
            "item_id": stack.definition_id,
            "label": stack.label,
            "quantity": stack.quantity,
            "tags": list(stack.tags),
            "verbs": _stack_area_view_verbs(stack),
            "is_container": bool(stack.is_container),
            "opened": is_stack_open(stack),
        }
        if stack.is_container and is_stack_open(stack):
            contents = [
                _stack_content_summary(child_stack)
                for child_stack in list_visible_area_container_child_stacks(
                    campaign,
                    stack.stack_id,
                    area_id=area_id,
                )
            ]
            if contents:
                view["contents"] = contents
        views.append(view)
    return views


def is_stack_container(stack: RuntimeItemStack) -> bool:
    return bool(stack.is_container)


def is_stack_open(stack: RuntimeItemStack) -> bool:
    return bool(stack.state.get("opened")) if stack.is_container else False


def is_stack_locked(stack: RuntimeItemStack) -> bool:
    return bool(stack.state.get("locked")) if stack.is_container else False


def set_stack_opened(
    campaign: Campaign,
    stack_id: str,
    *,
    opened: bool = True,
) -> RuntimeItemStack:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    stack.state["opened"] = bool(opened)
    validate_and_sync_campaign_items(campaign)
    return stack


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


def is_stack_visible_to_actor(
    campaign: Campaign,
    stack_id: str,
    *,
    actor_id: str,
    current_area_id: str | None,
) -> bool:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        return False
    current = stack
    visited = {stack.stack_id}
    while current.parent_type == "item":
        parent = get_stack_or_none(campaign, current.parent_id)
        if parent is None or parent.stack_id in visited:
            return False
        if not parent.is_container or not is_stack_open(parent):
            return False
        visited.add(parent.stack_id)
        current = parent
    if current.parent_type == "area":
        return isinstance(current_area_id, str) and current.parent_id == current_area_id
    if current.parent_type == "actor":
        return current.parent_id == actor_id
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


def list_container_child_stacks(
    campaign: Campaign,
    container_stack_id: str,
) -> List[RuntimeItemStack]:
    container = get_stack_or_none(campaign, container_stack_id)
    if container is None or not container.is_container:
        return []
    children: List[RuntimeItemStack] = []
    for stack_id in sorted(campaign.items.keys()):
        stack = get_stack_or_none(campaign, stack_id)
        if stack is None:
            continue
        if stack.parent_type != "item" or stack.parent_id != container.stack_id:
            continue
        children.append(stack)
    return children


def list_visible_container_child_stacks(
    campaign: Campaign,
    container_stack_id: str,
    *,
    actor_id: str,
    current_area_id: str | None,
) -> List[RuntimeItemStack]:
    container = get_stack_or_none(campaign, container_stack_id)
    if container is None or not container.is_container or not is_stack_open(container):
        return []
    if not is_stack_visible_to_actor(
        campaign,
        container.stack_id,
        actor_id=actor_id,
        current_area_id=current_area_id,
    ):
        return []
    return [
        stack
        for stack in list_container_child_stacks(campaign, container.stack_id)
        if is_stack_visible_to_actor(
            campaign,
            stack.stack_id,
            actor_id=actor_id,
            current_area_id=current_area_id,
        )
    ]


def list_visible_area_container_child_stacks(
    campaign: Campaign,
    container_stack_id: str,
    *,
    area_id: str | None,
) -> List[RuntimeItemStack]:
    if not isinstance(area_id, str) or not area_id.strip():
        return []
    return list_visible_container_child_stacks(
        campaign,
        container_stack_id,
        actor_id="",
        current_area_id=area_id,
    )


def search_stack_container_contents(
    campaign: Campaign,
    stack_id: str,
    *,
    actor_id: str,
    current_area_id: str | None,
) -> List[RuntimeItemStack]:
    return list_visible_container_child_stacks(
        campaign,
        stack_id,
        actor_id=actor_id,
        current_area_id=current_area_id,
    )


def search_area_item_sources(
    campaign: Campaign,
    area_id: str | None,
) -> Optional[Tuple[RuntimeItemStack, Optional[RuntimeItemStack]]]:
    for stack in list_area_root_stacks(campaign, area_id):
        if stack.is_container:
            if not is_stack_open(stack):
                continue
            children = list_visible_area_container_child_stacks(
                campaign,
                stack.stack_id,
                area_id=area_id,
            )
            if children:
                return stack, children[0]
            continue
        return stack, None
    return None


def can_actor_use_stack(
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
    if root_type != "actor" or root_id != actor_id:
        return False
    return is_stack_visible_to_actor(
        campaign,
        stack_id,
        actor_id=actor_id,
        current_area_id=current_area_id,
    )


def resolve_usable_stack(
    campaign: Campaign,
    actor_id: str,
    *,
    current_area_id: str | None,
    explicit_item_ref: str | None = None,
    selected_stack_id: str | None = None,
    selected_item_id: str | None = None,
) -> Optional[RuntimeItemStack]:
    normalized_explicit_ref = _read_string(explicit_item_ref)
    if normalized_explicit_ref:
        stack = resolve_selected_stack(
            campaign,
            actor_id,
            selected_stack_id=normalized_explicit_ref,
        )
        if stack is None:
            stack = resolve_selected_stack(
                campaign,
                actor_id,
                selected_item_id=normalized_explicit_ref,
            )
        if stack is None:
            return None
        return (
            stack
            if can_actor_use_stack(
                campaign,
                stack.stack_id,
                actor_id=actor_id,
                current_area_id=current_area_id,
            )
            else None
        )

    stack = resolve_selected_stack(
        campaign,
        actor_id,
        selected_stack_id=_read_string(selected_stack_id),
        selected_item_id=_read_string(selected_item_id),
    )
    if stack is None:
        return None
    return (
        stack
        if can_actor_use_stack(
            campaign,
            stack.stack_id,
            actor_id=actor_id,
            current_area_id=current_area_id,
        )
        else None
    )


def should_consume_stack_on_use(stack: RuntimeItemStack) -> bool:
    state_flag = stack.state.get("consume_on_use")
    if isinstance(state_flag, bool):
        return state_flag
    props_flag = stack.props.get("consume_on_use")
    return bool(props_flag) if isinstance(props_flag, bool) else False


def consume_stack_quantity(
    campaign: Campaign,
    *,
    stack_id: str,
    quantity: int = 1,
) -> Optional[RuntimeItemStack]:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    normalized_quantity = quantity if isinstance(quantity, int) else 0
    if normalized_quantity <= 0:
        raise ValueError("consume quantity must be positive")
    if stack.quantity < normalized_quantity:
        raise ValueError(f"insufficient stack quantity: {stack_id}")
    stack.quantity -= normalized_quantity
    if stack.quantity <= 0:
        del campaign.items[stack.stack_id]
        validate_and_sync_campaign_items(campaign)
        return None
    validate_and_sync_campaign_items(campaign)
    return stack


def split_stack(
    campaign: Campaign,
    *,
    stack_id: str,
    quantity: int,
) -> RuntimeItemStack:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    normalized_quantity = _normalize_positive_quantity(quantity, label="split quantity")
    if normalized_quantity > stack.quantity:
        raise ValueError(f"insufficient stack quantity: {stack_id}")
    if normalized_quantity == stack.quantity:
        return stack
    if not stack.stackable:
        raise ValueError(f"stack cannot be split: {stack_id}")

    source_before = stack.model_copy(deep=True)
    split_stack = _create_split_stack(
        campaign,
        source_stack=stack,
        quantity=normalized_quantity,
    )
    stack.quantity -= normalized_quantity
    campaign.items[split_stack.stack_id] = split_stack
    try:
        validate_and_sync_campaign_items(campaign)
    except Exception:
        campaign.items[source_before.stack_id] = source_before
        campaign.items.pop(split_stack.stack_id, None)
        validate_and_sync_campaign_items(campaign)
        raise
    created = get_stack_or_none(campaign, split_stack.stack_id)
    if created is None:
        raise ValueError(f"split stack missing after creation: {split_stack.stack_id}")
    return created


def move_stack_quantity(
    campaign: Campaign,
    *,
    stack_id: str,
    parent_type: str,
    parent_id: str,
    quantity: int | None = None,
    allow_merge: bool = True,
) -> RuntimeItemStack:
    stack = get_stack_or_none(campaign, stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    normalized_quantity = (
        stack.quantity
        if quantity is None
        else _normalize_positive_quantity(quantity, label="move quantity")
    )
    if normalized_quantity > stack.quantity:
        raise ValueError(f"insufficient stack quantity: {stack_id}")

    normalized_parent_type, normalized_parent_id = _normalize_destination_parent(
        stack,
        parent_type=parent_type,
        parent_id=parent_id,
    )
    merge_target = (
        _find_merge_target_in_destination(
            campaign,
            source_stack=stack,
            parent_type=normalized_parent_type,
            parent_id=normalized_parent_id,
            exclude_stack_id=stack.stack_id,
        )
        if allow_merge
        else None
    )

    if normalized_quantity == stack.quantity:
        if merge_target is not None:
            stack_before = stack.model_copy(deep=True)
            merge_target_before = merge_target.model_copy(deep=True)
            merge_target.quantity += stack.quantity
            del campaign.items[stack.stack_id]
            try:
                validate_and_sync_campaign_items(campaign)
            except Exception:
                campaign.items[stack_before.stack_id] = stack_before
                campaign.items[merge_target_before.stack_id] = merge_target_before
                validate_and_sync_campaign_items(campaign)
                raise
            merged = get_stack_or_none(campaign, merge_target.stack_id)
            if merged is None:
                raise ValueError(f"merged stack missing after move: {merge_target.stack_id}")
            return merged

        stack_before = stack.model_copy(deep=True)
        stack.parent_type = normalized_parent_type  # type: ignore[assignment]
        stack.parent_id = normalized_parent_id
        try:
            validate_and_sync_campaign_items(campaign)
        except Exception:
            campaign.items[stack_before.stack_id] = stack_before
            validate_and_sync_campaign_items(campaign)
            raise
        moved = get_stack_or_none(campaign, stack.stack_id)
        if moved is None:
            raise ValueError(f"moved stack missing after transfer: {stack.stack_id}")
        return moved

    moved_stack = split_stack(campaign, stack_id=stack_id, quantity=normalized_quantity)
    merge_target = (
        _find_merge_target_in_destination(
            campaign,
            source_stack=moved_stack,
            parent_type=normalized_parent_type,
            parent_id=normalized_parent_id,
            exclude_stack_id=moved_stack.stack_id,
        )
        if allow_merge
        else None
    )
    if merge_target is not None:
        moved_before = moved_stack.model_copy(deep=True)
        merge_target_before = merge_target.model_copy(deep=True)
        merge_target.quantity += moved_stack.quantity
        del campaign.items[moved_stack.stack_id]
        try:
            validate_and_sync_campaign_items(campaign)
        except Exception:
            campaign.items[moved_before.stack_id] = moved_before
            campaign.items[merge_target_before.stack_id] = merge_target_before
            validate_and_sync_campaign_items(campaign)
            raise
        merged = get_stack_or_none(campaign, merge_target.stack_id)
        if merged is None:
            raise ValueError(f"merged stack missing after partial move: {merge_target.stack_id}")
        return merged

    moved_before = moved_stack.model_copy(deep=True)
    moved_stack.parent_type = normalized_parent_type  # type: ignore[assignment]
    moved_stack.parent_id = normalized_parent_id
    try:
        validate_and_sync_campaign_items(campaign)
    except Exception:
        campaign.items[moved_before.stack_id] = moved_before
        validate_and_sync_campaign_items(campaign)
        raise
    moved = get_stack_or_none(campaign, moved_stack.stack_id)
    if moved is None:
        raise ValueError(f"moved stack missing after partial transfer: {moved_stack.stack_id}")
    return moved


def transfer_stack_parent(
    campaign: Campaign,
    *,
    stack_id: str,
    parent_type: str,
    parent_id: str,
    allow_merge: bool = False,
) -> RuntimeItemStack:
    return move_stack_quantity(
        campaign,
        stack_id=stack_id,
        parent_type=parent_type,
        parent_id=parent_id,
        quantity=None,
        allow_merge=allow_merge,
    )


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


def _stack_area_view_verbs(stack: RuntimeItemStack) -> List[str]:
    verbs = _normalize_text_list(stack.verbs)
    if stack.parent_type == "area" and "take" not in verbs:
        verbs.append("take")
    if stack.is_container:
        if "open" not in verbs:
            verbs.append("open")
        if is_stack_open(stack):
            if "search" not in verbs:
                verbs.append("search")
        else:
            verbs = [verb for verb in verbs if verb != "search"]
        return verbs
    return [verb for verb in verbs if verb not in {"open", "search"}]


def _stack_content_summary(stack: RuntimeItemStack) -> Dict[str, Any]:
    return {
        "item_id": stack.definition_id,
        "label": stack.label,
        "quantity": stack.quantity,
        "is_container": bool(stack.is_container),
        "opened": is_stack_open(stack),
    }


def _normalize_text_list(values: object) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    seen: set[str] = set()
    for raw_value in values:
        if not isinstance(raw_value, str):
            continue
        value = raw_value.strip().lower()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _read_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_positive_quantity(value: object, *, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be positive")
    return value


def _normalize_destination_parent(
    stack: RuntimeItemStack,
    *,
    parent_type: str,
    parent_id: str,
) -> Tuple[str, str]:
    candidate = create_runtime_item_stack(
        stack_id=stack.stack_id,
        definition_id=stack.definition_id,
        quantity=stack.quantity,
        parent_type=parent_type,
        parent_id=parent_id,
        metadata=stack.metadata,
        label=stack.label,
        description=stack.description,
        tags=stack.tags,
        verbs=stack.verbs,
        state=stack.state,
        props=stack.props,
        stackable=stack.stackable,
        is_container=stack.is_container,
    )
    return candidate.parent_type, candidate.parent_id


def _find_merge_target_in_destination(
    campaign: Campaign,
    *,
    source_stack: RuntimeItemStack,
    parent_type: str,
    parent_id: str,
    exclude_stack_id: str,
) -> Optional[RuntimeItemStack]:
    if not source_stack.stackable:
        return None
    for candidate_stack_id in sorted(campaign.items.keys()):
        candidate = get_stack_or_none(campaign, candidate_stack_id)
        if candidate is None or candidate.stack_id == exclude_stack_id:
            continue
        if _can_merge_in_destination(
            source_stack,
            candidate,
            parent_type=parent_type,
            parent_id=parent_id,
        ):
            return candidate
    return None


def _can_merge_in_destination(
    source_stack: RuntimeItemStack,
    destination_stack: RuntimeItemStack,
    *,
    parent_type: str,
    parent_id: str,
) -> bool:
    if not source_stack.stackable or not destination_stack.stackable:
        return False
    if destination_stack.parent_type != parent_type or destination_stack.parent_id != parent_id:
        return False
    if source_stack.definition_id != destination_stack.definition_id:
        return False
    return dict(source_stack.metadata) == dict(destination_stack.metadata)


def _create_split_stack(
    campaign: Campaign,
    *,
    source_stack: RuntimeItemStack,
    quantity: int,
) -> RuntimeItemStack:
    counter = 0
    while True:
        salt = (
            f"split:{source_stack.stack_id}:{quantity}"
            if counter == 0
            else f"split:{source_stack.stack_id}:{quantity}:{counter}"
        )
        split_candidate = create_runtime_item_stack(
            definition_id=source_stack.definition_id,
            quantity=quantity,
            parent_type=source_stack.parent_type,
            parent_id=source_stack.parent_id,
            metadata=source_stack.metadata,
            label=source_stack.label,
            description=source_stack.description,
            tags=source_stack.tags,
            verbs=source_stack.verbs,
            state=source_stack.state,
            props=source_stack.props,
            stackable=source_stack.stackable,
            is_container=source_stack.is_container,
            stack_id_salt=salt,
        )
        if split_candidate.stack_id not in campaign.items:
            return split_candidate
        counter += 1


__all__ = [
    "build_area_root_stack_views",
    "can_actor_use_stack",
    "carry_mass_limit",
    "compute_actor_item_mass",
    "compute_entity_mass",
    "compute_stack_mass",
    "consume_stack_quantity",
    "get_stack_or_none",
    "is_area_root_stack_visible",
    "is_stack_container",
    "is_stack_locked",
    "is_stack_open",
    "is_direct_actor_stack",
    "is_stack_reachable",
    "is_stack_visible_to_actor",
    "list_container_child_stacks",
    "list_area_root_stacks",
    "list_visible_area_container_child_stacks",
    "list_visible_container_child_stacks",
    "move_stack_quantity",
    "resolve_usable_stack",
    "search_area_item_sources",
    "search_stack_container_contents",
    "set_stack_opened",
    "should_consume_stack_on_use",
    "split_stack",
    "transfer_stack_parent",
    "would_exceed_actor_carry_limit",
]
