from __future__ import annotations

import shutil
from pathlib import Path

from backend.infra.file_repo import FileRepo


def _copy_fixture_campaign(tmp_path: Path) -> FileRepo:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = (
        repo_root / "backend" / "tests" / "fixtures" / "campaigns" / "camp_item_stack_fixture"
    )
    target_dir = tmp_path / "storage" / "campaigns" / "camp_item_stack_fixture"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_dir / "campaign.json", target_dir / "campaign.json")
    return FileRepo(tmp_path / "storage")


def test_item_stack_fixture_loads_from_items_and_derives_compat_inventory(
    tmp_path: Path,
) -> None:
    repo = _copy_fixture_campaign(tmp_path)

    campaign = repo.get_campaign("camp_item_stack_fixture")

    assert sorted(campaign.items.keys()) == [
        "stk_fixture_ration_actor",
        "stk_fixture_rope_remote",
        "stk_fixture_tonic_actor",
        "stk_fixture_torch_ground_start",
    ]
    assert campaign.actors["ch_e3cd4e96"].inventory == {
        "field_ration": 1,
        "healing_tonic": 2,
    }
    assert campaign.items["stk_fixture_tonic_actor"].parent_type == "actor"
    assert campaign.items["stk_fixture_tonic_actor"].parent_id == "ch_e3cd4e96"
    assert campaign.items["stk_fixture_torch_ground_start"].parent_type == "area"
    assert campaign.items["stk_fixture_torch_ground_start"].parent_id == "area_start"
    assert campaign.items["stk_fixture_rope_remote"].parent_type == "area"
    assert campaign.items["stk_fixture_rope_remote"].parent_id == "area_gate"
    assert campaign.entities == {}
