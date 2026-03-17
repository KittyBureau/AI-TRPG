from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Dict, Iterable, Optional, Tuple

from backend.domain.models import Campaign, RuntimeItemStack

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_ID_SLUG_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_SUPPORTED_PARENT_TYPES = {"actor", "area", "item"}


@dataclass(frozen=True)
class SelectedStackResolution:
    requested_item_id: str
    requested_stack_id: str
    resolved_item_id: str
    resolved_stack_id: str
    status: str
    reason: str
    resolved_stack: Optional[RuntimeItemStack] = None


def create_runtime_item_stack(
    *,
    definition_id: str,
    quantity: int,
    parent_type: str,
    parent_id: str,
    stack_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[object]] = None,
    verbs: Optional[Iterable[object]] = None,
    state: Optional[Dict[str, Any]] = None,
    props: Optional[Dict[str, Any]] = None,
    stackable: bool = True,
    is_container: bool = False,
    stack_id_salt: Optional[str] = None,
) -> RuntimeItemStack:
    normalized_definition_id = _normalize_required_id(definition_id, label="definition_id")
    normalized_parent_type = _normalize_parent_type(parent_type)
    normalized_parent_id = _normalize_required_id(parent_id, label="parent_id")
    normalized_stackable = bool(stackable)
    normalized_is_container = bool(is_container)
    if normalized_is_container:
        normalized_stackable = False
    normalized_quantity = _normalize_quantity(quantity)
    if not normalized_stackable and normalized_quantity != 1:
        raise ValueError("non-stackable items must have quantity=1")
    normalized_stack_id = _normalize_or_create_stack_id(
        stack_id,
        definition_id=normalized_definition_id,
        salt=stack_id_salt or f"{normalized_parent_type}:{normalized_parent_id}",
    )
    normalized_label = _normalize_label(label, fallback=normalized_definition_id)
    normalized_description = _normalize_optional_text(description)
    return RuntimeItemStack(
        stack_id=normalized_stack_id,
        definition_id=normalized_definition_id,
        quantity=normalized_quantity,
        parent_type=normalized_parent_type,  # type: ignore[arg-type]
        parent_id=normalized_parent_id,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
        label=normalized_label,
        description=normalized_description,
        tags=_normalize_text_list(tags),
        verbs=_normalize_text_list(verbs),
        state=dict(state) if isinstance(state, dict) else {},
        props=dict(props) if isinstance(props, dict) else {},
        stackable=normalized_stackable,
        is_container=normalized_is_container,
    )


def normalize_campaign_items(campaign: Campaign) -> bool:
    updated = False

    raw_items = campaign.items if isinstance(campaign.items, dict) else {}
    if not isinstance(campaign.items, dict):
        campaign.items = {}
        updated = True

    normalized_items: Dict[str, RuntimeItemStack] = {}
    for raw_key, raw_value in raw_items.items():
        stack = _coerce_runtime_item_stack(raw_key, raw_value)
        if stack.stack_id in normalized_items:
            raise ValueError(f"duplicate item stack_id: {stack.stack_id}")
        normalized_items[stack.stack_id] = stack
        raw_payload = (
            raw_value.model_dump() if isinstance(raw_value, RuntimeItemStack) else raw_value
        )
        if raw_key != stack.stack_id or raw_payload != stack.model_dump():
            updated = True

    if not normalized_items and _campaign_has_legacy_inventory_only_state(campaign):
        raise ValueError(
            "inventory-only campaign payloads are unsupported; initialize campaign.items instead"
        )

    campaign.items = normalized_items
    _validate_item_graph(campaign)

    if _sync_derived_actor_inventories(campaign):
        updated = True

    return updated


def validate_and_sync_campaign_items(campaign: Campaign) -> None:
    _validate_item_graph(campaign)
    _sync_derived_actor_inventories(campaign)


def derive_actor_inventory(campaign: Campaign, actor_id: str) -> Dict[str, int]:
    return derive_actor_inventory_from_items_only(campaign, actor_id)


def derive_actor_inventory_from_items_only(
    campaign: Campaign, actor_id: str
) -> Dict[str, int]:
    return _derive_actor_inventory_from_items(campaign, actor_id)


def derive_all_actor_inventories_from_items_only(
    campaign: Campaign,
) -> Dict[str, Dict[str, int]]:
    inventories: Dict[str, Dict[str, int]] = {}
    for actor_id in sorted(campaign.actors.keys()):
        inventories[actor_id] = _derive_actor_inventory_from_items(campaign, actor_id)
    return inventories


def derive_actor_inventory_stack_ids_from_items_only(
    campaign: Campaign,
    actor_id: str,
) -> Dict[str, list[str]]:
    stack_ids_by_definition: Dict[str, list[str]] = {}
    for stack in _list_actor_owned_stacks_from_items(campaign, actor_id):
        stack_ids_by_definition.setdefault(stack.definition_id, []).append(stack.stack_id)
    return {
        definition_id: stack_ids_by_definition[definition_id]
        for definition_id in sorted(stack_ids_by_definition.keys())
    }


def derive_all_actor_inventory_stack_ids_from_items_only(
    campaign: Campaign,
) -> Dict[str, Dict[str, list[str]]]:
    stack_ids_by_actor: Dict[str, Dict[str, list[str]]] = {}
    for actor_id in sorted(campaign.actors.keys()):
        stack_ids_by_actor[actor_id] = derive_actor_inventory_stack_ids_from_items_only(
            campaign, actor_id
        )
    return stack_ids_by_actor


def get_actor_item_quantity_from_items_only(
    campaign: Campaign,
    actor_id: str,
    definition_id: str,
) -> int:
    if not isinstance(definition_id, str):
        return 0
    item_id = definition_id.strip()
    if not item_id:
        return 0
    return _derive_actor_inventory_from_items(campaign, actor_id).get(item_id, 0)


def resolve_selected_stack(
    campaign: Campaign,
    actor_id: str,
    *,
    selected_stack_id: Optional[str] = None,
    selected_item_id: Optional[str] = None,
) -> Optional[RuntimeItemStack]:
    return resolve_selected_stack_resolution(
        campaign,
        actor_id,
        selected_stack_id=selected_stack_id,
        selected_item_id=selected_item_id,
    ).resolved_stack


def resolve_selected_stack_resolution(
    campaign: Campaign,
    actor_id: str,
    *,
    selected_stack_id: Optional[str] = None,
    selected_item_id: Optional[str] = None,
) -> SelectedStackResolution:
    normalized_stack_id = _read_string(selected_stack_id)
    normalized_item_id = _read_string(selected_item_id)
    if normalized_stack_id:
        stack = campaign.items.get(normalized_stack_id)
        if stack is None:
            return SelectedStackResolution(
                requested_item_id=normalized_item_id,
                requested_stack_id=normalized_stack_id,
                resolved_item_id="",
                resolved_stack_id="",
                status="none",
                reason="explicit_stack_missing",
            )
        try:
            root_type, root_id = resolve_stack_root(campaign, normalized_stack_id)
        except ValueError:
            return SelectedStackResolution(
                requested_item_id=normalized_item_id,
                requested_stack_id=normalized_stack_id,
                resolved_item_id="",
                resolved_stack_id="",
                status="none",
                reason="explicit_stack_invalid",
            )
        if root_type != "actor" or root_id != actor_id:
            return SelectedStackResolution(
                requested_item_id=normalized_item_id,
                requested_stack_id=normalized_stack_id,
                resolved_item_id="",
                resolved_stack_id="",
                status="none",
                reason="explicit_stack_not_actor_owned",
            )
        if not isinstance(stack.quantity, int) or stack.quantity <= 0:
            return SelectedStackResolution(
                requested_item_id=normalized_item_id,
                requested_stack_id=normalized_stack_id,
                resolved_item_id="",
                resolved_stack_id="",
                status="none",
                reason="explicit_stack_invalid",
            )
        return SelectedStackResolution(
            requested_item_id=normalized_item_id,
            requested_stack_id=normalized_stack_id,
            resolved_item_id=stack.definition_id,
            resolved_stack_id=stack.stack_id,
            status="stack_explicit",
            reason="explicit_stack_valid",
            resolved_stack=stack,
        )

    if not normalized_item_id:
        return SelectedStackResolution(
            requested_item_id="",
            requested_stack_id="",
            resolved_item_id="",
            resolved_stack_id="",
            status="none",
            reason="no_hint",
        )
    stack_ids = derive_actor_inventory_stack_ids_from_items_only(campaign, actor_id).get(
        normalized_item_id, []
    )
    if not stack_ids:
        return SelectedStackResolution(
            requested_item_id=normalized_item_id,
            requested_stack_id="",
            resolved_item_id="",
            resolved_stack_id="",
            status="none",
            reason="item_match_missing",
        )
    stack = campaign.items.get(stack_ids[0])
    if stack is None or not isinstance(stack.quantity, int) or stack.quantity <= 0:
        return SelectedStackResolution(
            requested_item_id=normalized_item_id,
            requested_stack_id="",
            resolved_item_id="",
            resolved_stack_id="",
            status="none",
            reason="item_match_invalid",
        )
    return SelectedStackResolution(
        requested_item_id=normalized_item_id,
        requested_stack_id="",
        resolved_item_id=stack.definition_id,
        resolved_stack_id=stack.stack_id,
        status="item_fallback",
        reason="item_match_found",
        resolved_stack=stack,
    )


def grant_item_to_actor(
    campaign: Campaign,
    *,
    actor_id: str,
    definition_id: str,
    quantity: int,
    label: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[object]] = None,
    verbs: Optional[Iterable[object]] = None,
    state: Optional[Dict[str, Any]] = None,
    props: Optional[Dict[str, Any]] = None,
    stackable: bool = True,
    is_container: bool = False,
    stack_id_salt: Optional[str] = None,
) -> RuntimeItemStack:
    normalize_campaign_items(campaign)
    if actor_id not in campaign.actors:
        raise ValueError(f"unknown actor item parent: {actor_id}")

    candidate = create_runtime_item_stack(
        definition_id=definition_id,
        quantity=quantity,
        parent_type="actor",
        parent_id=actor_id,
        label=label,
        description=description,
        tags=tags,
        verbs=verbs,
        state=state,
        props=props,
        stackable=stackable,
        is_container=is_container,
        stack_id_salt=stack_id_salt or f"actor:{actor_id}:{definition_id}",
    )

    if candidate.stackable:
        merge_target = _find_merge_target(campaign, candidate)
        if merge_target is not None:
            merge_target.quantity += candidate.quantity
            _sync_derived_actor_inventories(campaign)
            return merge_target

    stack = candidate
    counter = 1
    while stack.stack_id in campaign.items:
        stack = create_runtime_item_stack(
            definition_id=candidate.definition_id,
            quantity=candidate.quantity,
            parent_type=candidate.parent_type,
            parent_id=candidate.parent_id,
            label=candidate.label,
            description=candidate.description,
            tags=candidate.tags,
            verbs=candidate.verbs,
            state=candidate.state,
            props=candidate.props,
            stackable=candidate.stackable,
            is_container=candidate.is_container,
            stack_id_salt=f"{stack_id_salt or f'actor:{actor_id}:{definition_id}'}:{counter}",
        )
        counter += 1

    campaign.items[stack.stack_id] = stack
    validate_and_sync_campaign_items(campaign)
    return stack


def resolve_stack_root(campaign: Campaign, stack_id: str) -> Tuple[str, str]:
    stack = campaign.items.get(stack_id)
    if stack is None:
        raise ValueError(f"missing item stack: {stack_id}")
    visited = {stack.stack_id}
    current = stack
    while current.parent_type == "item":
        parent = campaign.items.get(current.parent_id)
        if parent is None:
            raise ValueError(f"missing parent item stack: {current.parent_id}")
        if parent.stack_id in visited:
            raise ValueError(f"item parent cycle detected: {parent.stack_id}")
        visited.add(parent.stack_id)
        current = parent
    return current.parent_type, current.parent_id


def _coerce_runtime_item_stack(raw_key: object, raw_value: object) -> RuntimeItemStack:
    if isinstance(raw_value, RuntimeItemStack):
        payload = raw_value.model_dump()
    elif isinstance(raw_value, dict):
        payload = dict(raw_value)
    else:
        raise ValueError(f"invalid item stack payload: {raw_key}")

    if "stack_id" not in payload and isinstance(raw_key, str) and raw_key.strip():
        payload["stack_id"] = raw_key.strip()

    return create_runtime_item_stack(
        stack_id=payload.get("stack_id"),
        definition_id=_read_string(payload.get("definition_id")),
        quantity=payload.get("quantity", 1),
        parent_type=_read_string(payload.get("parent_type")),
        parent_id=_read_string(payload.get("parent_id")),
        metadata=payload.get("metadata"),
        label=payload.get("label"),
        description=payload.get("description"),
        tags=payload.get("tags"),
        verbs=payload.get("verbs"),
        state=payload.get("state"),
        props=payload.get("props"),
        stackable=payload.get("stackable", True)
        if isinstance(payload.get("stackable", True), bool)
        else True,
        is_container=payload.get("is_container", False)
        if isinstance(payload.get("is_container", False), bool)
        else False,
    )


def _validate_item_graph(campaign: Campaign) -> None:
    for stack in campaign.items.values():
        if stack.parent_type == "actor":
            if stack.parent_id not in campaign.actors:
                raise ValueError(f"unknown actor item parent: {stack.parent_id}")
            continue
        if stack.parent_type == "area":
            if stack.parent_id not in campaign.map.areas:
                raise ValueError(f"unknown area item parent: {stack.parent_id}")
            continue
        if stack.parent_type != "item":
            raise ValueError(f"unsupported item parent_type: {stack.parent_type}")
        parent_stack = campaign.items.get(stack.parent_id)
        if parent_stack is None:
            raise ValueError(f"missing parent item stack: {stack.parent_id}")
        if not parent_stack.is_container:
            raise ValueError(f"item parent must be a container stack: {stack.parent_id}")

    for stack_id in sorted(campaign.items.keys()):
        resolve_stack_root(campaign, stack_id)


def _derive_actor_inventory_from_items(campaign: Campaign, actor_id: str) -> Dict[str, int]:
    inventory: Dict[str, int] = {}
    for stack in _list_actor_owned_stacks_from_items(campaign, actor_id):
        inventory[stack.definition_id] = inventory.get(stack.definition_id, 0) + stack.quantity
    return dict(sorted(inventory.items()))


def _list_actor_owned_stacks_from_items(
    campaign: Campaign, actor_id: str
) -> list[RuntimeItemStack]:
    stacks: list[RuntimeItemStack] = []
    for stack_id in sorted(campaign.items.keys()):
        stack = campaign.items.get(stack_id)
        if stack is None:
            continue
        try:
            root_type, root_id = resolve_stack_root(campaign, stack_id)
        except ValueError:
            continue
        if root_type != "actor" or root_id != actor_id:
            continue
        stacks.append(stack)
    return stacks


def _sync_derived_actor_inventories(campaign: Campaign) -> bool:
    updated = False
    for actor_id, actor in campaign.actors.items():
        expected_inventory = _derive_actor_inventory_from_items(campaign, actor_id)
        current_inventory = actor.inventory if isinstance(actor.inventory, dict) else {}
        if current_inventory != expected_inventory:
            actor.inventory = expected_inventory
            updated = True
    return updated


def _campaign_has_legacy_inventory_only_state(campaign: Campaign) -> bool:
    for actor in campaign.actors.values():
        if not isinstance(actor.inventory, dict):
            continue
        if any(
            isinstance(item_id, str)
            and item_id.strip()
            and isinstance(quantity, int)
            and quantity > 0
            for item_id, quantity in actor.inventory.items()
        ):
            return True
    return False


def _find_merge_target(
    campaign: Campaign, candidate: RuntimeItemStack
) -> Optional[RuntimeItemStack]:
    signature = _merge_signature(candidate)
    for stack in campaign.items.values():
        if not stack.stackable:
            continue
        if _merge_signature(stack) == signature:
            return stack
    return None


def _merge_signature(stack: RuntimeItemStack) -> Tuple[object, ...]:
    return (
        stack.definition_id,
        stack.parent_type,
        stack.parent_id,
        tuple(sorted(stack.metadata.items())),
        stack.label,
        stack.description,
        tuple(stack.tags),
        tuple(stack.verbs),
        tuple(sorted(stack.state.items())),
        tuple(sorted(stack.props.items())),
        stack.stackable,
        stack.is_container,
    )


def _normalize_required_id(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is required")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} is required")
    if _SAFE_ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"invalid {label}: {value}")
    return normalized


def _normalize_parent_type(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("parent_type is required")
    normalized = value.strip().lower()
    if normalized not in _SUPPORTED_PARENT_TYPES:
        raise ValueError(f"invalid parent_type: {value}")
    return normalized


def _normalize_quantity(value: object) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError("quantity must be a positive integer")
    return value


def _normalize_label(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip()
    return normalized or fallback


def _normalize_optional_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text_list(values: Optional[Iterable[object]]) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        if not isinstance(raw_value, str):
            continue
        text = raw_value.strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _normalize_or_create_stack_id(
    raw_stack_id: object,
    *,
    definition_id: str,
    salt: str,
) -> str:
    if isinstance(raw_stack_id, str) and raw_stack_id.strip():
        return _normalize_required_id(raw_stack_id, label="stack_id")
    slug = _ID_SLUG_PATTERN.sub("_", definition_id).strip("_") or "item"
    suffix = hashlib.sha1(f"{definition_id}:{salt}".encode("utf-8")).hexdigest()[:8]
    return f"stk_{slug}_{suffix}"


def _read_string(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


__all__ = [
    "SelectedStackResolution",
    "create_runtime_item_stack",
    "derive_actor_inventory",
    "derive_actor_inventory_from_items_only",
    "derive_all_actor_inventories_from_items_only",
    "derive_actor_inventory_stack_ids_from_items_only",
    "derive_all_actor_inventory_stack_ids_from_items_only",
    "grant_item_to_actor",
    "get_actor_item_quantity_from_items_only",
    "normalize_campaign_items",
    "resolve_selected_stack",
    "resolve_selected_stack_resolution",
    "resolve_stack_root",
    "validate_and_sync_campaign_items",
]
