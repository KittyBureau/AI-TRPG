from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from backend.domain.models import Campaign
from backend.domain.world_models import World, stable_world_timestamp
from backend.infra.file_repo import FileRepo


def generate_world(
    args: Dict[str, Any],
    campaign: Campaign,
    repo: FileRepo,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    world_id_arg, error = _parse_world_id_arg(args)
    if error:
        return None, error
    bind_to_campaign, error = _parse_bool_arg(args, "bind_to_campaign", default=False)
    if error:
        return None, error
    also_generate_map, error = _parse_bool_arg(args, "also_generate_map", default=False)
    if error:
        return None, error
    seed_arg, error = _parse_seed_arg(args)
    if error:
        return None, error
    generator_id_arg, error = _parse_generator_id_arg(args)
    if error:
        return None, error

    resolved_world_id = _resolve_world_id(world_id_arg, campaign)
    if resolved_world_id is None:
        return None, "world_id_missing"

    world = repo.get_world(resolved_world_id)
    created = world is None
    if world is None:
        world = repo.get_or_create_world_stub(resolved_world_id)

    normalized = _normalize_world_v1(
        world,
        world_id=resolved_world_id,
        seed_arg=seed_arg,
        generator_id_arg=generator_id_arg,
        created=created,
    )
    if normalized:
        repo.save_world(world)

    if bind_to_campaign:
        campaign.selected.world_id = resolved_world_id
    bound_to_campaign = bind_to_campaign and campaign.selected.world_id == resolved_world_id

    result = {
        "world_id": resolved_world_id,
        "created": created,
        "normalized": normalized,
        "bound_to_campaign": bound_to_campaign,
        "seed": world.seed,
        "generator_id": world.generator.id,
        "also_generate_map": also_generate_map,
    }
    return result, None


def _parse_world_id_arg(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    raw = args.get("world_id")
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, "invalid_args"
    trimmed = raw.strip()
    if not trimmed:
        return None, None
    return trimmed, None


def _parse_bool_arg(
    args: Dict[str, Any],
    key: str,
    *,
    default: bool,
) -> Tuple[bool, Optional[str]]:
    raw = args.get(key, default)
    if isinstance(raw, bool):
        return raw, None
    return False, "invalid_args"


def _parse_seed_arg(args: Dict[str, Any]) -> Tuple[Optional[int | str], Optional[str]]:
    raw = args.get("seed")
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return None, "invalid_args"
    if isinstance(raw, int) or isinstance(raw, str):
        return raw, None
    return None, "invalid_args"


def _parse_generator_id_arg(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    raw = args.get("generator_id")
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, "invalid_args"
    trimmed = raw.strip()
    if not trimmed:
        return None, "invalid_args"
    return trimmed, None


def _resolve_world_id(world_id_arg: Optional[str], campaign: Campaign) -> Optional[str]:
    if world_id_arg:
        return world_id_arg
    selected_world_id = campaign.selected.world_id.strip()
    if selected_world_id:
        return selected_world_id
    return None


def _normalize_world_v1(
    world: World,
    *,
    world_id: str,
    seed_arg: Optional[int | str],
    generator_id_arg: Optional[str],
    created: bool,
) -> bool:
    changed = False
    now = stable_world_timestamp(world_id)

    if not world.world_id.strip():
        world.world_id = world_id
        changed = True

    if not world.name.strip():
        world.name = world.world_id
        changed = True

    if not world.world_description.strip():
        world.world_description = (
            "A sparse frontier of connected rooms and uncertain paths."
        )
        changed = True

    if not world.objective.strip():
        world.objective = "Explore the nearby areas and recover one useful item."
        changed = True

    if not world.start_area.strip():
        world.start_area = "area_001"
        changed = True

    if not world.schema_version.strip():
        world.schema_version = "1"
        changed = True

    if not world.generator.id.strip():
        world.generator.id = generator_id_arg or "stub"
        changed = True

    if not world.generator.version.strip():
        world.generator.version = "1"
        changed = True

    if not isinstance(world.generator.params, dict):
        world.generator.params = {}
        changed = True

    seed_changed, seed_source = _apply_seed_policy(
        world,
        world_id=world_id,
        seed_arg=seed_arg,
        created=created,
    )
    if seed_changed:
        changed = True
    seed_source_value = world.generator.params.get("seed_source")
    if not isinstance(seed_source_value, str) or not seed_source_value.strip():
        world.generator.params["seed_source"] = seed_source
        changed = True

    created_at = world.created_at.strip()
    if not created_at:
        world.created_at = now
        changed = True

    updated_at = world.updated_at.strip()
    if not updated_at:
        world.updated_at = world.created_at
        changed = True

    return changed


def _apply_seed_policy(
    world: World,
    *,
    world_id: str,
    seed_arg: Optional[int | str],
    created: bool,
) -> Tuple[bool, str]:
    seed_source = "world_id_hash"
    changed = False
    seed_missing = False
    if isinstance(world.seed, str):
        seed_missing = not world.seed.strip()
    elif not isinstance(world.seed, int):
        seed_missing = True

    if seed_missing:
        if seed_arg is not None:
            world.seed = seed_arg
            seed_source = "args.seed"
        else:
            world.seed = stable_seed_from_world_id(world_id)
            seed_source = "world_id_hash"
        return True, seed_source

    if created and seed_arg is not None and world.seed != seed_arg:
        world.seed = seed_arg
        changed = True
        seed_source = "args.seed"

    return changed, seed_source
