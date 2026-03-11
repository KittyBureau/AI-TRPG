from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.actor_service import spawn_actor
from backend.app.character_facade_factory import create_runtime_character_facade
from backend.app.world_presets import is_goal_area, required_item_for_move
from backend.app.world_service import generate_world
from backend.domain.character_access import (
    CharacterFacade,
    CharacterState,
)
from backend.domain.models import (
    AppliedAction,
    Campaign,
    Entity,
    EntityLocation,
    FailedCall,
    ToolCall,
    ToolFeedback,
)
from backend.domain.map_models import normalize_map, require_valid_map
from backend.domain.state_machine import resolve_tool_permission
from backend.infra.map_generators.deterministic_generator import (
    DeterministicMapGenerator,
)
from backend.infra.file_repo import FileRepo


def execute_tool_calls(
    campaign: Campaign,
    actor_id: str,
    tool_calls: List[ToolCall],
    *,
    repo: Optional[FileRepo] = None,
) -> Tuple[List[AppliedAction], Optional[ToolFeedback]]:
    applied_actions: List[AppliedAction] = []
    failed_calls: List[FailedCall] = []
    character_facade = create_runtime_character_facade()

    for call in tool_calls:
        actor_context_ok, actor_context_reason = _check_actor_context_consistency(
            actor_id, call
        )
        if not actor_context_ok:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason=actor_context_reason,
                )
            )
            continue

        if call.tool not in campaign.allowlist:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason="tool_not_allowed",
                )
            )
            continue

        allowed, reason = _check_state_permission(
            campaign, actor_id, call, character_facade
        )
        if not allowed:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason=reason,
                )
            )
            continue

        action, error_reason = _apply_tool_call(
            campaign, actor_id, call, character_facade, repo=repo
        )
        if action is None:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="error",
                    reason=error_reason or "invalid_args",
                )
            )
            continue

        applied_actions.append(action)

    tool_feedback = ToolFeedback(failed_calls=failed_calls) if failed_calls else None
    return applied_actions, tool_feedback


def _check_actor_context_consistency(
    effective_actor_id: str,
    call: ToolCall,
) -> Tuple[bool, str]:
    if "actor_id" not in call.args:
        return True, ""
    raw_actor_id = call.args.get("actor_id")
    if not isinstance(raw_actor_id, str):
        return False, "invalid_args"
    actor_id = raw_actor_id.strip()
    if not actor_id:
        return False, "invalid_args"
    if actor_id != effective_actor_id:
        return False, "actor_context_mismatch"
    if actor_id != raw_actor_id:
        call.args["actor_id"] = actor_id
    return True, ""


def _resolve_call_actor_id(effective_actor_id: str, call: ToolCall) -> Optional[str]:
    actor_id = call.args.get("actor_id")
    if actor_id is None:
        return effective_actor_id
    if not isinstance(actor_id, str):
        return None
    return actor_id


def _check_state_permission(
    campaign: Campaign,
    actor_id: str,
    call: ToolCall,
    character_facade: CharacterFacade,
) -> Tuple[bool, str]:
    if actor_id in campaign.actors:
        actor_state = character_facade.get_state(campaign, actor_id).character_state
    else:
        actor_state = "alive"
    target_is_actor = False
    hp_delta: Optional[int] = None
    if call.tool == "hp_delta":
        target_is_actor = call.args.get("target_character_id") == actor_id
        delta = call.args.get("delta")
        if isinstance(delta, int):
            hp_delta = delta

    return resolve_tool_permission(
        actor_state, call.tool, target_is_actor=target_is_actor, hp_delta=hp_delta
    )


def _apply_tool_call(
    campaign: Campaign,
    actor_id: str,
    call: ToolCall,
    character_facade: CharacterFacade,
    *,
    repo: Optional[FileRepo],
) -> Tuple[Optional[AppliedAction], Optional[str]]:
    timestamp = datetime.now(timezone.utc).isoformat()
    if call.tool == "move":
        return _apply_move(campaign, actor_id, call, timestamp, character_facade)
    if call.tool == "hp_delta":
        action = _apply_hp_delta(campaign, call, timestamp, character_facade)
        return action, "invalid_args" if action is None else None
    if call.tool == "inventory_add":
        return _apply_inventory_add(
            campaign, actor_id, call, timestamp, character_facade
        )
    if call.tool == "move_options":
        action = _apply_move_options(
            campaign, actor_id, call, timestamp, character_facade
        )
        return action, "invalid_args" if action is None else None
    if call.tool == "map_generate":
        action = _apply_map_generate(campaign, call, timestamp)
        return action, "invalid_args" if action is None else None
    if call.tool == "world_generate":
        return _apply_world_generate(campaign, call, timestamp, repo=repo)
    if call.tool == "actor_spawn":
        return _apply_actor_spawn(campaign, actor_id, call, timestamp)
    if call.tool == "scene_action":
        action = _apply_scene_action(
            campaign, actor_id, call, timestamp, character_facade
        )
        return action, "invalid_args" if action is None else None
    return None, "invalid_args"


def _apply_move(
    campaign: Campaign,
    effective_actor_id: str,
    call: ToolCall,
    timestamp: str,
    character_facade: CharacterFacade,
) -> Tuple[Optional[AppliedAction], Optional[str]]:
    actor_id = _resolve_call_actor_id(effective_actor_id, call)
    to_area_id = call.args.get("to_area_id")
    if "from_area_id" in call.args:
        return None, "invalid_args"
    if not isinstance(actor_id, str) or not isinstance(to_area_id, str):
        return None, "invalid_args"
    if actor_id not in campaign.actors:
        return None, "invalid_args"
    if to_area_id not in campaign.map.areas:
        return None, "invalid_args"
    actor_state = character_facade.get_state(campaign, actor_id)
    from_area_id = actor_state.position
    if not isinstance(from_area_id, str):
        return None, "invalid_args"
    if to_area_id == from_area_id:
        return None, "invalid_args"
    if not _is_connected(campaign, from_area_id, to_area_id):
        return None, "invalid_args"
    required_item_id = required_item_for_move(
        campaign.selected.world_id, from_area_id, to_area_id
    )
    if required_item_id is not None:
        actor = campaign.actors.get(actor_id)
        inventory = actor.inventory if actor is not None and isinstance(actor.inventory, dict) else {}
        quantity = inventory.get(required_item_id)
        if not isinstance(quantity, int) or quantity <= 0:
            return None, "missing_required_item"
    character_facade.set_state(
        campaign,
        actor_id,
        CharacterState(
            position=to_area_id,
            hp=actor_state.hp,
            character_state=actor_state.character_state,
        ),
    )
    if is_goal_area(campaign.selected.world_id, to_area_id):
        campaign.goal.status = "completed"
    return AppliedAction(
        tool="move",
        args=call.args,
        result={"from_area_id": from_area_id, "to_area_id": to_area_id},
        timestamp=timestamp,
    ), None


def _apply_hp_delta(
    campaign: Campaign,
    call: ToolCall,
    timestamp: str,
    character_facade: CharacterFacade,
) -> Optional[AppliedAction]:
    target_id = call.args.get("target_character_id")
    delta = call.args.get("delta")
    cause = call.args.get("cause")
    if not isinstance(target_id, str) or not isinstance(delta, int):
        return None
    if not isinstance(cause, str):
        return None
    if target_id not in campaign.actors:
        return None
    state = character_facade.get_state(campaign, target_id)

    new_hp = state.hp + delta
    if new_hp < 0:
        new_hp = 0
    next_character_state = state.character_state
    if campaign.settings_snapshot.rules.hp_zero_ends_game:
        if new_hp <= 0:
            next_character_state = "dying"
        elif next_character_state == "dying":
            next_character_state = "alive"
    character_facade.set_state(
        campaign,
        target_id,
        CharacterState(
            position=state.position,
            hp=new_hp,
            character_state=next_character_state,
        ),
    )
    return AppliedAction(
        tool="hp_delta",
        args=call.args,
        result={"new_hp": new_hp},
        timestamp=timestamp,
    )


def _apply_inventory_add(
    campaign: Campaign,
    effective_actor_id: str,
    call: ToolCall,
    timestamp: str,
    character_facade: CharacterFacade,
) -> Tuple[Optional[AppliedAction], Optional[str]]:
    actor_id = _resolve_call_actor_id(effective_actor_id, call)
    item_id = call.args.get("item_id")
    quantity = call.args.get("quantity", 1)
    source_entity_id = call.args.get("source_entity_id")
    if not isinstance(actor_id, str):
        return None, "invalid_args"
    if not isinstance(item_id, str):
        return None, "invalid_args"
    normalized_item_id = item_id.strip()
    if not normalized_item_id:
        return None, "invalid_args"
    if not isinstance(quantity, int) or quantity <= 0:
        return None, "invalid_args"
    if not isinstance(source_entity_id, str) or not source_entity_id.strip():
        return None, "inventory_source_required"
    actor_state = character_facade.get_state(campaign, actor_id)
    character_facade.set_state(campaign, actor_id, actor_state)
    new_qty, error_reason = _grant_inventory_from_source(
        campaign,
        actor_id=actor_id,
        item_id=normalized_item_id,
        quantity=quantity,
        source_entity_id=source_entity_id.strip(),
    )
    if new_qty is None:
        return None, error_reason or "invalid_item_source"
    return AppliedAction(
        tool="inventory_add",
        args=call.args,
        result={
            "actor_id": actor_id,
            "item_id": normalized_item_id,
            "quantity_added": quantity,
            "new_quantity": new_qty,
        },
        timestamp=timestamp,
    ), None


def _apply_move_options(
    campaign: Campaign,
    effective_actor_id: str,
    call: ToolCall,
    timestamp: str,
    character_facade: CharacterFacade,
) -> Optional[AppliedAction]:
    actor_id = _resolve_call_actor_id(effective_actor_id, call)
    if not isinstance(actor_id, str):
        return None
    if actor_id not in campaign.actors:
        return None
    current_area_id = character_facade.get_state(campaign, actor_id).position
    if not isinstance(current_area_id, str):
        return None
    area = campaign.map.areas.get(current_area_id)
    if area is None:
        return None
    options = []
    for to_area_id in sorted(area.reachable_area_ids):
        target_area = campaign.map.areas.get(to_area_id)
        name = target_area.name if target_area else ""
        options.append({"to_area_id": to_area_id, "name": name})
    return AppliedAction(
        tool="move_options",
        args=call.args,
        result={"options": options},
        timestamp=timestamp,
    )


def _apply_map_generate(
    campaign: Campaign, call: ToolCall, timestamp: str
) -> Optional[AppliedAction]:
    parent_area_id = call.args.get("parent_area_id", None)
    if parent_area_id is not None and not isinstance(parent_area_id, str):
        return None
    if parent_area_id is not None and parent_area_id not in campaign.map.areas:
        return None

    theme = call.args.get("theme", "Generated")
    if theme is None:
        theme = "Generated"
    if not isinstance(theme, str):
        return None

    constraints = call.args.get("constraints")
    size = 6
    seed: Optional[str] = None
    if isinstance(constraints, dict):
        if "size" in constraints:
            size_value = constraints.get("size")
            if not isinstance(size_value, int):
                return None
            size = size_value
        if "seed" in constraints:
            seed_value = constraints.get("seed")
            if seed_value is not None and not isinstance(seed_value, str):
                return None
            seed = seed_value
    elif constraints is not None:
        return None
    else:
        if "size" in call.args:
            size_value = call.args.get("size")
            if not isinstance(size_value, int):
                return None
            size = size_value
        if "seed" in call.args:
            seed_value = call.args.get("seed")
            if seed_value is not None and not isinstance(seed_value, str):
                return None
            seed = seed_value

    if size < 1 or size > 30:
        return None

    if hasattr(campaign.map, "model_copy"):
        snapshot = campaign.map.model_copy(deep=True)
    elif hasattr(campaign.map, "copy"):
        snapshot = campaign.map.copy(deep=True)
    else:
        snapshot = deepcopy(campaign.map)

    before_connections = sum(
        len(area.reachable_area_ids) for area in campaign.map.areas.values()
    )

    try:
        generator = DeterministicMapGenerator()
        result = generator.generate(
            campaign.map, parent_area_id, theme, size, seed
        )
        if not _is_valid_map_generation_result(snapshot, result):
            campaign.map = snapshot
            return None

        for area_id, area in result.new_areas.items():
            campaign.map.areas[area_id] = area
        for from_id, to_id in result.new_edges:
            if from_id not in campaign.map.areas or to_id not in campaign.map.areas:
                campaign.map = snapshot
                return None
            reachable = campaign.map.areas[from_id].reachable_area_ids
            if to_id not in reachable:
                reachable.append(to_id)

        if parent_area_id is not None:
            parent_area = campaign.map.areas.get(parent_area_id)
            if parent_area is None:
                campaign.map = snapshot
                return None
            for area_id in result.created_area_ids:
                if area_id == parent_area_id:
                    continue
                if area_id not in parent_area.reachable_area_ids:
                    parent_area.reachable_area_ids.append(area_id)
                child_area = campaign.map.areas.get(area_id)
                if child_area is None:
                    campaign.map = snapshot
                    return None
                if parent_area_id not in child_area.reachable_area_ids:
                    child_area.reachable_area_ids.append(parent_area_id)

        require_valid_map(campaign.map)
        normalize_map(campaign.map)
    except Exception:
        campaign.map = snapshot
        return None
    after_connections = sum(
        len(area.reachable_area_ids) for area in campaign.map.areas.values()
    )
    return AppliedAction(
        tool="map_generate",
        args=call.args,
        result={
            "created_area_ids": result.created_area_ids,
            "created_connections": after_connections - before_connections,
            "root_parent_area_id": parent_area_id,
            "warnings": result.warnings,
        },
        timestamp=timestamp,
    )


def _is_valid_map_generation_result(existing_map: Any, result: Any) -> bool:
    if not hasattr(result, "new_areas") or not hasattr(result, "created_area_ids"):
        return False
    if not hasattr(result, "new_edges") or not hasattr(result, "warnings"):
        return False
    if not isinstance(result.new_areas, dict):
        return False
    if not isinstance(result.created_area_ids, list):
        return False
    if not isinstance(result.new_edges, list):
        return False

    created_ids = []
    for area_id in result.created_area_ids:
        if not isinstance(area_id, str) or not area_id.strip():
            return False
        created_ids.append(area_id)
    if len(created_ids) != len(set(created_ids)):
        return False
    if set(created_ids) != set(result.new_areas.keys()):
        return False
    if any(area_id in existing_map.areas for area_id in created_ids):
        return False

    for area_id, area in result.new_areas.items():
        if not isinstance(area_id, str) or not area_id.strip():
            return False
        if not hasattr(area, "id") or not hasattr(area, "reachable_area_ids"):
            return False
        if getattr(area, "id", None) != area_id:
            return False

    for edge in result.new_edges:
        if not isinstance(edge, tuple) or len(edge) != 2:
            return False
        from_id, to_id = edge
        if not isinstance(from_id, str) or not isinstance(to_id, str):
            return False

    return True


def _apply_world_generate(
    campaign: Campaign,
    call: ToolCall,
    timestamp: str,
    *,
    repo: Optional[FileRepo],
) -> Tuple[Optional[AppliedAction], Optional[str]]:
    if repo is None:
        return None, "invalid_args"
    result, error = generate_world(call.args, campaign, repo)
    if result is None:
        return None, error or "invalid_args"
    return (
        AppliedAction(
            tool="world_generate",
            args=call.args,
            result=result,
            timestamp=timestamp,
        ),
        None,
    )


def _apply_actor_spawn(
    campaign: Campaign,
    effective_actor_id: str,
    call: ToolCall,
    timestamp: str,
) -> Tuple[Optional[AppliedAction], Optional[str]]:
    result, error = spawn_actor(
        call.args, campaign, active_actor_id=effective_actor_id
    )
    if result is None:
        return None, error or "invalid_args"
    return (
        AppliedAction(
            tool="actor_spawn",
            args=call.args,
            result=result,
            timestamp=timestamp,
        ),
        None,
    )


SCENE_ACTIONS = {
    "inspect",
    "talk",
    "open",
    "search",
    "take",
    "drop",
    "detach",
    "use",
    "wait",
}

PORTABLE_ENTITY_KINDS = {"item", "object", "container"}
DEFAULT_CARRY_MASS_LIMIT = 60.0
DEFAULT_ENTITY_MASS = 1.0


def _apply_scene_action(
    campaign: Campaign,
    effective_actor_id: str,
    call: ToolCall,
    timestamp: str,
    character_facade: CharacterFacade,
) -> Optional[AppliedAction]:
    actor_id = _resolve_call_actor_id(effective_actor_id, call)
    action = call.args.get("action")
    target_id = call.args.get("target_id")
    params = call.args.get("params", {})

    if not isinstance(actor_id, str):
        return None
    if actor_id not in campaign.actors:
        return None
    if not isinstance(action, str):
        return None
    if not isinstance(params, dict):
        return None
    normalized_action = action.strip().lower()
    if normalized_action not in SCENE_ACTIONS:
        return None

    if normalized_action == "wait":
        normalized_target_id = target_id.strip() if isinstance(target_id, str) else ""
    else:
        if not isinstance(target_id, str):
            return None
        normalized_target_id = target_id.strip()
        if not normalized_target_id:
            return None

    actor_state = character_facade.get_state(campaign, actor_id)
    current_area_id = actor_state.position

    target: Optional[Entity] = None
    is_area_search = False
    if normalized_action not in {"wait"}:
        target = campaign.entities.get(normalized_target_id)
        if target is None:
            if (
                normalized_action == "search"
                and isinstance(current_area_id, str)
                and normalized_target_id == current_area_id
            ):
                is_area_search = True
            else:
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative="You cannot find that target here.",
                        error_code="target_not_found",
                        error_message=f"target not found: {normalized_target_id}",
                    ),
                )

    if target is not None:
        if not _is_entity_reachable(
            campaign, target, actor_id=actor_id, current_area_id=current_area_id
        ):
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=False,
                    narrative=f"{target.label} is not reachable right now.",
                    error_code="not_reachable",
                    error_message=f"target not reachable: {target.id}",
                ),
            )
        if not _is_scene_action_allowed(normalized_action, target):
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=False,
                    narrative=f"You cannot {normalized_action} {target.label}.",
                    error_code="not_allowed",
                    error_message=f"action not allowed: {normalized_action}",
                ),
            )

    entity_patches: List[Dict[str, Any]] = []
    new_entities: List[Dict[str, Any]] = []
    removed_entities: List[Dict[str, Any]] = []
    entities_before = deepcopy(campaign.entities)
    try:
        if normalized_action == "inspect":
            label = target.label if target is not None else "the scene"
            hint_suffix = _scene_hint_suffix(target)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You inspect {label}.{hint_suffix}",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "talk":
            if target is None:
                return None
            hint_suffix = _scene_hint_suffix(target)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You talk to {target.label}.{hint_suffix}",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "open":
            if target is None:
                return None
            if target.state.get("locked") is True:
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"{target.label} is locked.",
                        error_code="locked",
                        error_message=f"target locked: {target.id}",
                        entity_patches=entity_patches,
                        new_entities=new_entities,
                        removed_entities=removed_entities,
                    ),
                )
            if target.state.get("opened") is not True:
                before = _entity_to_dict(target)
                target.state["opened"] = True
                _append_entity_patch(entity_patches, target, before)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You open {target.label}.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "search":
            if is_area_search:
                area_source = _find_area_inventory_source(
                    campaign,
                    actor_id=actor_id,
                    area_id=current_area_id,
                )
                if area_source is not None:
                    source_entity, item_id, quantity = area_source
                    new_qty, error_reason = _grant_inventory_from_source(
                        campaign,
                        actor_id=actor_id,
                        item_id=item_id,
                        quantity=quantity,
                        source_entity_id=source_entity.id,
                        entity_patches=entity_patches,
                    )
                    if new_qty is not None:
                        return _scene_action_applied(
                            call,
                            timestamp,
                            _scene_action_result(
                                ok=True,
                                narrative=f"You search the area and find {item_id} in {source_entity.label}.",
                                entity_patches=entity_patches,
                                new_entities=new_entities,
                                removed_entities=removed_entities,
                            ),
                        )
                    if error_reason == "item_source_depleted":
                        return _scene_action_applied(
                            call,
                            timestamp,
                            _scene_action_result(
                                ok=True,
                                narrative="You search the area but find nothing useful.",
                                entity_patches=entity_patches,
                                new_entities=new_entities,
                                removed_entities=removed_entities,
                            ),
                        )
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=True,
                        narrative="You search the area but find nothing new.",
                        entity_patches=entity_patches,
                        new_entities=new_entities,
                        removed_entities=removed_entities,
                    ),
                )
            if target is None:
                return None
            grant_item_id = target.state.get("inventory_item_id")
            grant_quantity = target.state.get("inventory_quantity", 1)
            if isinstance(grant_item_id, str):
                normalized_grant_item_id = grant_item_id.strip()
                if normalized_grant_item_id and isinstance(grant_quantity, int) and grant_quantity > 0:
                    new_qty, error_reason = _grant_inventory_from_source(
                        campaign,
                        actor_id=actor_id,
                        item_id=normalized_grant_item_id,
                        quantity=grant_quantity,
                        source_entity_id=target.id,
                        entity_patches=entity_patches,
                    )
                    if new_qty is not None:
                        return _scene_action_applied(
                            call,
                            timestamp,
                            _scene_action_result(
                                ok=True,
                                narrative=f"You search {target.label} and find {normalized_grant_item_id}.",
                                entity_patches=entity_patches,
                                new_entities=new_entities,
                                removed_entities=removed_entities,
                            ),
                        )
                    if error_reason == "item_source_depleted":
                        return _scene_action_applied(
                            call,
                            timestamp,
                            _scene_action_result(
                                ok=True,
                                narrative=f"You search {target.label} but find nothing useful.",
                                entity_patches=entity_patches,
                                new_entities=new_entities,
                                removed_entities=removed_entities,
                            ),
                        )
            if target.kind == "container" and target.state.get("opened") is True:
                has_nested = any(
                    entity.loc.type == "entity" and entity.loc.id == target.id
                    for entity in campaign.entities.values()
                )
                if not has_nested:
                    spawned = Entity(
                        id=_next_spawn_entity_id(campaign, target.id),
                        kind="item",
                        label=f"{target.label} Trinket",
                        tags=["loot"],
                        loc=EntityLocation(type="entity", id=target.id),
                        verbs=["inspect", "take"],
                        state={},
                        props={"mass": 1},
                    )
                    campaign.entities[spawned.id] = spawned
                    new_entities.append(_entity_to_dict(spawned))
                    return _scene_action_applied(
                        call,
                        timestamp,
                        _scene_action_result(
                            ok=True,
                            narrative=f"You search {target.label} and find {spawned.label}.",
                            entity_patches=entity_patches,
                            new_entities=new_entities,
                            removed_entities=removed_entities,
                        ),
                    )
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You search {target.label} but find nothing useful.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "take":
            if target is None:
                return None
            if target.kind == "npc":
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"You cannot take {target.label}.",
                        error_code="not_allowed",
                        error_message=f"target is not portable: {target.id}",
                    ),
                )
            if target.loc.type == "actor" and target.loc.id == actor_id:
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"{target.label} is already in your inventory.",
                        error_code="not_allowed",
                        error_message="target already in actor inventory",
                    ),
                )
            if _exceeds_carry_limit(campaign, actor_id, target):
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"{target.label} is too heavy to carry.",
                        error_code="carry_limit",
                        error_message=f"carry limit exceeded by target: {target.id}",
                    ),
                )
            before = _entity_to_dict(target)
            if target.kind == "object":
                target.kind = "item"
            target.loc = EntityLocation(type="actor", id=actor_id)
            target.verbs = _verbs_for_inventory(target.verbs)
            _append_entity_patch(entity_patches, target, before)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You take {target.label}.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "drop":
            if target is None:
                return None
            if not isinstance(current_area_id, str) or not current_area_id.strip():
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative="You cannot drop items without a valid area.",
                        error_code="not_reachable",
                        error_message="actor has no active area",
                    ),
                )
            if not (target.loc.type == "actor" and target.loc.id == actor_id):
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"{target.label} is not in your inventory.",
                        error_code="not_allowed",
                        error_message=f"target not in actor inventory: {target.id}",
                    ),
                )
            before = _entity_to_dict(target)
            target.loc = EntityLocation(type="area", id=current_area_id)
            target.verbs = _verbs_for_ground(target.verbs, target.kind)
            _append_entity_patch(entity_patches, target, before)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You drop {target.label}.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "detach":
            if target is None:
                return None
            if _exceeds_carry_limit(campaign, actor_id, target):
                return _scene_action_applied(
                    call,
                    timestamp,
                    _scene_action_result(
                        ok=False,
                        narrative=f"{target.label} is too heavy to detach and carry.",
                        error_code="carry_limit",
                        error_message=f"carry limit exceeded by target: {target.id}",
                    ),
                )
            before = _entity_to_dict(target)
            target.kind = "item"
            target.state["detached"] = True
            target.loc = EntityLocation(type="actor", id=actor_id)
            target.verbs = _verbs_for_inventory(target.verbs)
            _append_entity_patch(entity_patches, target, before)
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=f"You detach {target.label}.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "use":
            if target is None:
                return None
            item_id = params.get("item_id")
            item_label = ""
            if item_id is not None:
                if not isinstance(item_id, str):
                    return _scene_action_applied(
                        call,
                        timestamp,
                        _scene_action_result(
                            ok=False,
                            narrative="You fumble for the wrong item.",
                            error_code="invalid_args",
                            error_message="params.item_id must be string",
                        ),
                    )
                normalized_item_id = item_id.strip()
                if not normalized_item_id:
                    return _scene_action_applied(
                        call,
                        timestamp,
                        _scene_action_result(
                            ok=False,
                            narrative="You need a specific item to use here.",
                            error_code="invalid_args",
                            error_message="params.item_id must be non-empty",
                        ),
                    )
                item = campaign.entities.get(normalized_item_id)
                if item is None or not (
                    item.loc.type == "actor" and item.loc.id == actor_id
                ):
                    return _scene_action_applied(
                        call,
                        timestamp,
                        _scene_action_result(
                            ok=False,
                            narrative="That item is not in your inventory.",
                            error_code="missing_item",
                            error_message=f"item not in actor inventory: {normalized_item_id}",
                        ),
                    )
                item_label = item.label
            before = _entity_to_dict(target)
            target.state["used"] = not bool(target.state.get("used"))
            _append_entity_patch(entity_patches, target, before)
            use_narrative = (
                f"You use {item_label} on {target.label}."
                if item_label
                else f"You use {target.label}."
            )
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative=use_narrative,
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        if normalized_action == "wait":
            return _scene_action_applied(
                call,
                timestamp,
                _scene_action_result(
                    ok=True,
                    narrative="You wait and observe the surroundings.",
                    entity_patches=entity_patches,
                    new_entities=new_entities,
                    removed_entities=removed_entities,
                ),
            )

        return None
    except Exception:
        campaign.entities = entities_before
        return _scene_action_applied(
            call,
            timestamp,
            _scene_action_result(
                ok=False,
                narrative="You cannot complete that action right now.",
            ),
        )


def _scene_action_applied(
    call: ToolCall, timestamp: str, result: Dict[str, Any]
) -> AppliedAction:
    return AppliedAction(
        tool="scene_action",
        args=call.args,
        result=result,
        timestamp=timestamp,
    )


def _scene_action_result(
    *,
    ok: bool,
    narrative: str,
    entity_patches: Optional[List[Dict[str, Any]]] = None,
    new_entities: Optional[List[Dict[str, Any]]] = None,
    removed_entities: Optional[List[Dict[str, Any]]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": ok,
        "narrative": narrative,
        "patches": {
            "entity_patches": entity_patches or [],
            "new_entities": new_entities or [],
            "removed_entities": removed_entities or [],
        },
    }
    if not ok:
        result["error"] = {
            "code": error_code or "scene_action_failed",
            "message": error_message or "scene action failed",
        }
    return result


def _normalized_verbs(raw_verbs: object) -> List[str]:
    if not isinstance(raw_verbs, list):
        return []
    seen: Set[str] = set()
    verbs: List[str] = []
    for raw in raw_verbs:
        if not isinstance(raw, str):
            continue
        normalized = raw.strip().lower()
        if not normalized or normalized in seen:
            continue
        verbs.append(normalized)
        seen.add(normalized)
    return verbs


def _verbs_for_inventory(raw_verbs: object) -> List[str]:
    verbs = [verb for verb in _normalized_verbs(raw_verbs) if verb not in {"take", "detach"}]
    if "drop" not in verbs:
        verbs.append("drop")
    return verbs


def _verbs_for_ground(raw_verbs: object, kind: str) -> List[str]:
    verbs = [verb for verb in _normalized_verbs(raw_verbs) if verb != "drop"]
    if kind in PORTABLE_ENTITY_KINDS and "take" not in verbs:
        verbs.append("take")
    return verbs


def _is_scene_action_allowed(action: str, target: Entity) -> bool:
    allowed_verbs = set(_normalized_verbs(target.verbs))
    blocked_verbs = set(_normalized_verbs(target.state.get("blocked_verbs")))
    if action == "inspect":
        if target.state.get("inspect_blocked") is True:
            return False
        return "inspect" not in blocked_verbs
    if action == "talk":
        return target.kind == "npc" or "talk" in allowed_verbs
    return action in allowed_verbs


def _is_entity_reachable(
    campaign: Campaign,
    target: Entity,
    *,
    actor_id: str,
    current_area_id: Optional[str],
) -> bool:
    root = _resolve_root_location(campaign, target, max_depth=3)
    if root is None:
        return False
    root_type, root_id = root
    if root_type == "area":
        return isinstance(current_area_id, str) and root_id == current_area_id
    if root_type == "actor":
        return root_id == actor_id
    return False


def _resolve_root_location(
    campaign: Campaign, target: Entity, *, max_depth: int
) -> Optional[Tuple[str, str]]:
    location = target.loc
    visited: Set[str] = {target.id}
    depth = 0
    while True:
        if location.type in {"area", "actor"}:
            return location.type, location.id
        if location.type != "entity":
            return None
        parent_id = location.id
        if not parent_id or parent_id in visited:
            return None
        parent = campaign.entities.get(parent_id)
        if parent is None:
            return None
        depth += 1
        if depth > max_depth:
            return None
        visited.add(parent_id)
        location = parent.loc


def _next_spawn_entity_id(campaign: Campaign, target_id: str) -> str:
    base = f"{target_id}_loot"
    counter = 1
    while True:
        candidate = f"{base}_{counter:02d}"
        if candidate not in campaign.entities:
            return candidate
        counter += 1


def _entity_to_dict(entity: Entity) -> Dict[str, Any]:
    if hasattr(entity, "model_dump"):
        return entity.model_dump()
    if hasattr(entity, "dict"):
        return entity.dict()
    return {}


def _append_entity_patch(
    entity_patches: List[Dict[str, Any]], entity: Entity, before: Dict[str, Any]
) -> None:
    after = _entity_to_dict(entity)
    if before == after:
        return
    changes: Dict[str, Any] = {}
    for key, value in after.items():
        if before.get(key) != value:
            changes[key] = value
    entity_patches.append({"id": entity.id, "changes": changes})


def _actor_inventory_mass(campaign: Campaign, actor_id: str) -> float:
    total = 0.0
    for entity in campaign.entities.values():
        if entity.loc.type != "actor" or entity.loc.id != actor_id:
            continue
        if entity.kind not in PORTABLE_ENTITY_KINDS:
            continue
        total += _entity_mass(entity)
    return total


def _entity_mass(entity: Entity) -> float:
    raw_mass = entity.props.get("mass")
    if isinstance(raw_mass, (int, float)) and raw_mass > 0:
        return float(raw_mass)
    return DEFAULT_ENTITY_MASS


def _carry_mass_limit(campaign: Campaign, actor_id: str) -> float:
    actor = campaign.actors.get(actor_id)
    if actor is None or not isinstance(actor.meta, dict):
        return DEFAULT_CARRY_MASS_LIMIT
    raw_limit = actor.meta.get("carry_mass_limit")
    if isinstance(raw_limit, (int, float)) and raw_limit > 0:
        return float(raw_limit)
    return DEFAULT_CARRY_MASS_LIMIT


def _exceeds_carry_limit(campaign: Campaign, actor_id: str, entity: Entity) -> bool:
    current_mass = _actor_inventory_mass(campaign, actor_id)
    limit = _carry_mass_limit(campaign, actor_id)
    return current_mass + _entity_mass(entity) > limit


def _is_connected(campaign: Campaign, from_area_id: str, to_area_id: str) -> bool:
    area = campaign.map.areas.get(from_area_id)
    if not area:
        return False
    return to_area_id in area.reachable_area_ids


def _scene_hint_suffix(target: Optional[Entity]) -> str:
    if target is None:
        return ""
    hint = target.state.get("hint")
    if not isinstance(hint, str):
        return ""
    normalized_hint = hint.strip()
    if not normalized_hint:
        return ""
    return f" {normalized_hint}"


def _grant_inventory_from_source(
    campaign: Campaign,
    *,
    actor_id: str,
    item_id: str,
    quantity: int,
    source_entity_id: str,
    entity_patches: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[int], Optional[str]]:
    actor = campaign.actors.get(actor_id)
    source = campaign.entities.get(source_entity_id)
    if actor is None or source is None:
        return None, "invalid_item_source"
    current_area_id = actor.position if isinstance(actor.position, str) else None
    if not _is_entity_reachable(
        campaign,
        source,
        actor_id=actor_id,
        current_area_id=current_area_id,
    ):
        return None, "invalid_item_source"
    granted_item_id = source.state.get("inventory_item_id")
    if not isinstance(granted_item_id, str) or granted_item_id.strip() != item_id:
        return None, "invalid_item_source"
    granted_quantity = source.state.get("inventory_quantity", 1)
    if not isinstance(granted_quantity, int) or granted_quantity <= 0:
        return None, "invalid_item_source"
    if quantity != granted_quantity:
        return None, "invalid_item_source"
    if source.state.get("inventory_granted") is True:
        return None, "item_source_depleted"
    before = _entity_to_dict(source) if entity_patches is not None else {}
    if not isinstance(actor.inventory, dict):
        actor.inventory = {}
    current_qty = actor.inventory.get(item_id, 0)
    if not isinstance(current_qty, int) or current_qty < 0:
        current_qty = 0
    new_qty = current_qty + quantity
    actor.inventory[item_id] = new_qty
    source.state["inventory_granted"] = True
    if entity_patches is not None:
        _append_entity_patch(entity_patches, source, before)
    return new_qty, None


def _find_area_inventory_source(
    campaign: Campaign,
    *,
    actor_id: str,
    area_id: Optional[str],
) -> Optional[Tuple[Entity, str, int]]:
    if not isinstance(area_id, str) or not area_id.strip():
        return None
    for entity in sorted(campaign.entities.values(), key=lambda item: item.id):
        if entity.loc.type != "area" or entity.loc.id != area_id:
            continue
        item_id = entity.state.get("inventory_item_id")
        quantity = entity.state.get("inventory_quantity", 1)
        if not isinstance(item_id, str) or not item_id.strip():
            continue
        if not isinstance(quantity, int) or quantity <= 0:
            continue
        if entity.state.get("inventory_granted") is True:
            continue
        if not _is_scene_action_allowed("search", entity):
            continue
        if not _is_entity_reachable(
            campaign,
            entity,
            actor_id=actor_id,
            current_area_id=area_id,
        ):
            continue
        return entity, item_id.strip(), quantity
    return None
