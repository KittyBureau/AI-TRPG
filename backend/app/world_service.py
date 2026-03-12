from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from backend.app.scenario_runtime_mapper import SCENARIO_GENERATOR_ID, SCENARIO_MODE
from backend.app.scenario_templates import normalize_scenario_params
from backend.app.world_presets import build_world_preset
from backend.domain.models import Campaign
from backend.domain.world_models import World, stable_seed_from_world_id, stable_world_timestamp
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

    world, created, normalized = _ensure_world_resource(
        world_id=resolved_world_id,
        repo=repo,
        name_arg=None,
        seed_arg=seed_arg,
        generator_id_arg=generator_id_arg,
    )

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


def generate_world_resource(
    *,
    world_id: str,
    repo: FileRepo,
    name: Optional[str] = None,
    generator_id: Optional[str] = None,
    generator_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_world_id = world_id.strip()
    if not normalized_world_id:
        raise ValueError("world_id is required")
    name_arg = name.strip() if isinstance(name, str) and name.strip() else None
    generator_id_arg, generator_params_arg = _normalize_generator_request(
        generator_id=generator_id,
        generator_params=generator_params,
    )
    world, created, normalized = _ensure_world_resource(
        world_id=normalized_world_id,
        repo=repo,
        name_arg=name_arg,
        seed_arg=None,
        generator_id_arg=generator_id_arg,
        generator_params_arg=generator_params_arg,
    )
    return {
        "world_id": world.world_id,
        "name": world.name,
        "seed": world.seed,
        "world_description": world.world_description,
        "objective": world.objective,
        "start_area": world.start_area,
        "generator": world.generator,
        "schema_version": world.schema_version,
        "created_at": world.created_at,
        "updated_at": world.updated_at,
        "created": created,
        "normalized": normalized,
    }


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


def _ensure_world_resource(
    *,
    world_id: str,
    repo: FileRepo,
    name_arg: Optional[str],
    seed_arg: Optional[int | str],
    generator_id_arg: Optional[str],
    generator_params_arg: Optional[Dict[str, Any]] = None,
) -> Tuple[World, bool, bool]:
    world = repo.get_world(world_id)
    created = world is None
    if world is None:
        preset_world = build_world_preset(world_id)
        if preset_world is not None:
            world = preset_world
            repo.save_world(world)
        else:
            world = repo.get_or_create_world_stub(world_id)

    normalized = _normalize_world_v1(
        world,
        world_id=world_id,
        name_arg=name_arg,
        seed_arg=seed_arg,
        generator_id_arg=generator_id_arg,
        generator_params_arg=generator_params_arg,
        created=created,
    )
    if normalized:
        repo.save_world(world)
    return world, created, normalized


def _normalize_world_v1(
    world: World,
    *,
    world_id: str,
    name_arg: Optional[str],
    seed_arg: Optional[int | str],
    generator_id_arg: Optional[str],
    generator_params_arg: Optional[Dict[str, Any]],
    created: bool,
) -> bool:
    changed = False
    now = stable_world_timestamp(world_id)

    if not world.world_id.strip():
        world.world_id = world_id
        changed = True

    if name_arg is not None and world.name != name_arg:
        world.name = name_arg
        changed = True
    elif not world.name.strip():
        world.name = world.world_id
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

    if _apply_generator_contract(
        world,
        generator_id_arg=generator_id_arg,
        generator_params_arg=generator_params_arg,
    ):
        changed = True

    if _is_playable_scenario_world(world):
        if not world.world_description.strip():
            world.world_description = (
                "A playable scenario world resource that stores normalized generator metadata only."
            )
            changed = True
        if not world.objective.strip():
            world.objective = "Find the required item and enter the target area."
            changed = True
        if world.start_area != "area_start":
            world.start_area = "area_start"
            changed = True
    else:
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

    seed_changed, seed_source = _apply_seed_policy(
        world,
        world_id=world_id,
        seed_arg=seed_arg,
        created=created,
    )
    if seed_changed:
        changed = True
    if _is_playable_scenario_world(world):
        if "seed_source" in world.generator.params:
            world.generator.params.pop("seed_source", None)
            changed = True
    else:
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


def _normalize_generator_request(
    *,
    generator_id: Optional[str],
    generator_params: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    generator_id_arg = (
        generator_id.strip() if isinstance(generator_id, str) and generator_id.strip() else None
    )
    if generator_params is not None and not isinstance(generator_params, dict):
        raise ValueError("generator_params must be an object")
    if generator_params is not None and generator_id_arg is None:
        raise ValueError("generator_id is required when generator_params are provided")
    if generator_id_arg is not None and generator_id_arg != SCENARIO_GENERATOR_ID:
        raise ValueError(f"unsupported generator_id: {generator_id_arg}")
    if generator_id_arg != SCENARIO_GENERATOR_ID:
        return generator_id_arg, None
    scenario_input = dict(generator_params or {})
    template_id = scenario_input.get("template_id")
    if "scenario_template" not in scenario_input and isinstance(template_id, str):
        scenario_input["scenario_template"] = template_id
    normalized = normalize_scenario_params(scenario_input)
    return generator_id_arg, {
        "mode": SCENARIO_MODE,
        "template_id": normalized.scenario_template,
        "template_version": "v0",
        "theme": normalized.theme,
        "area_count": normalized.area_count,
        "layout_type": normalized.layout_type,
        "difficulty": normalized.difficulty,
    }


def _apply_generator_contract(
    world: World,
    *,
    generator_id_arg: Optional[str],
    generator_params_arg: Optional[Dict[str, Any]],
) -> bool:
    if generator_id_arg != SCENARIO_GENERATOR_ID and generator_params_arg is None:
        return False
    changed = False
    if world.generator.id != SCENARIO_GENERATOR_ID:
        world.generator.id = SCENARIO_GENERATOR_ID
        changed = True
    if world.generator.version != "1":
        world.generator.version = "1"
        changed = True
    if generator_params_arg is not None and world.generator.params != generator_params_arg:
        world.generator.params = dict(generator_params_arg)
        changed = True
    return changed


def _is_playable_scenario_world(world: World) -> bool:
    if world.generator.id != SCENARIO_GENERATOR_ID:
        return False
    if not isinstance(world.generator.params, dict):
        return False
    return (
        world.generator.params.get("mode") == SCENARIO_MODE
        and world.generator.params.get("template_id") == "key_gate_scenario"
    )


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
