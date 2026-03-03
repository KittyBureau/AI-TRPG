from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Union

from pydantic import BaseModel, Field


class WorldGenerator(BaseModel):
    id: str = "stub"
    version: str = "1"
    params: Dict[str, Any] = Field(default_factory=dict)


class World(BaseModel):
    world_id: str
    name: str
    seed: Union[int, str]
    generator: WorldGenerator = Field(default_factory=WorldGenerator)
    schema_version: str = "1"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def stable_seed_from_world_id(world_id: str) -> int:
    digest = hashlib.sha256(world_id.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**31)


def normalize_world(world: World) -> None:
    world.world_id = world.world_id.strip()
    world.name = world.name.strip() or world.world_id
    world.schema_version = world.schema_version.strip() or "1"
    if not world.generator.id.strip():
        world.generator.id = "stub"
    if not world.generator.version.strip():
        world.generator.version = "1"


def require_valid_world(world: World) -> None:
    normalize_world(world)
    errors = []
    if not world.world_id:
        errors.append("world_id_empty")
    if not world.name:
        errors.append("name_empty")
    if not world.schema_version:
        errors.append("schema_version_empty")
    if not world.generator.id:
        errors.append("generator_id_empty")
    if not world.generator.version:
        errors.append("generator_version_empty")
    if errors:
        raise ValueError("invalid_world:" + ",".join(errors))


def build_world_stub(
    world_id: str,
    *,
    seed_source: str = "world_id_hash",
    generator_default: str = "stub",
) -> World:
    normalized_world_id = world_id.strip()
    now = datetime.now(timezone.utc).isoformat()
    seed = stable_seed_from_world_id(normalized_world_id)
    world = World(
        world_id=normalized_world_id,
        name=normalized_world_id,
        seed=seed,
        generator=WorldGenerator(
            id=generator_default,
            version="1",
            params={"seed_source": seed_source},
        ),
        schema_version="1",
        created_at=now,
        updated_at=now,
    )
    require_valid_world(world)
    return world
