from __future__ import annotations

from pathlib import Path

from backend.domain.world_models import World
from backend.infra.file_repo import FileRepo


def test_save_and_get_world_roundtrip(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    world = World(
        world_id="world_001",
        name="world_001",
        seed=123,
        generator={"id": "stub", "version": "1", "params": {}},
        schema_version="1",
        created_at="2026-03-03T00:00:00+00:00",
        updated_at="2026-03-03T00:00:00+00:00",
    )

    repo.save_world(world)
    loaded = repo.get_world("world_001")

    assert loaded is not None
    assert loaded.world_id == "world_001"
    assert loaded.seed == 123
    assert loaded.generator.id == "stub"


def test_get_world_returns_none_when_missing(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    assert repo.get_world("world_404") is None


def test_get_or_create_world_stub_is_idempotent(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")

    first = repo.get_or_create_world_stub("world_abc")
    second = repo.get_or_create_world_stub("world_abc")

    assert first.world_id == "world_abc"
    assert second.world_id == "world_abc"
    assert first.seed == second.seed
    assert second.generator.params.get("seed_source") == "world_id_hash"


def test_get_or_create_world_stub_is_deterministic_across_storage_roots(
    tmp_path: Path,
) -> None:
    first_repo = FileRepo(tmp_path / "one" / "storage")
    second_repo = FileRepo(tmp_path / "two" / "storage")

    first = first_repo.get_or_create_world_stub("world_abc")
    second = second_repo.get_or_create_world_stub("world_abc")

    first_path = tmp_path / "one" / "storage" / "worlds" / "world_abc" / "world.json"
    second_path = tmp_path / "two" / "storage" / "worlds" / "world_abc" / "world.json"
    if hasattr(first, "model_dump"):
        assert first.model_dump() == second.model_dump()
    else:
        assert first.dict() == second.dict()
    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")
