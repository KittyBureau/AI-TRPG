from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.item_runtime import (
    create_runtime_item_stack,
    derive_actor_inventory_from_items_only,
    derive_all_actor_inventories_from_items_only,
    get_actor_item_quantity_from_items_only,
)
from backend.app.turn_service import TurnService
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


def _base_campaign(campaign_id: str = "camp_items_phase1") -> Campaign:
    return Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="Start area",
                    reachable_area_ids=[],
                )
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={"rope": 2},
                meta={},
            )
        },
    )


def test_repo_migrates_legacy_actor_inventory_into_campaign_items(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _base_campaign()

    repo.create_campaign(campaign)
    reloaded = repo.get_campaign(campaign.id)

    assert reloaded.actors["pc_001"].inventory == {"rope": 2}
    assert len(reloaded.items) == 1
    only_stack = next(iter(reloaded.items.values()))
    assert only_stack.definition_id == "rope"
    assert only_stack.quantity == 2
    assert only_stack.parent_type == "actor"
    assert only_stack.parent_id == "pc_001"


def test_repo_rejects_item_parent_that_is_not_a_container(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    parent_stack = create_runtime_item_stack(
        definition_id="stone",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Stone",
        stackable=False,
        is_container=False,
        stack_id_salt="test:stone",
    )
    child_stack = create_runtime_item_stack(
        definition_id="coin",
        quantity=1,
        parent_type="item",
        parent_id=parent_stack.stack_id,
        label="Coin",
        stack_id_salt="test:coin",
    )
    campaign = _base_campaign("camp_items_parent_invalid")
    campaign.actors["pc_001"].inventory = {}
    campaign.items = {
        parent_stack.stack_id: parent_stack,
        child_stack.stack_id: child_stack,
    }

    with pytest.raises(ValueError, match="container stack"):
        repo.create_campaign(campaign)


def test_repo_rejects_item_parent_cycle(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    first = create_runtime_item_stack(
        definition_id="bag",
        quantity=1,
        parent_type="item",
        parent_id="stk_box_deadbeef",
        label="Bag",
        stackable=False,
        is_container=True,
        stack_id="stk_bag_deadbeef",
    )
    second = create_runtime_item_stack(
        definition_id="box",
        quantity=1,
        parent_type="item",
        parent_id=first.stack_id,
        label="Box",
        stackable=False,
        is_container=True,
        stack_id="stk_box_deadbeef",
    )
    first.parent_id = second.stack_id
    campaign = _base_campaign("camp_items_cycle_invalid")
    campaign.actors["pc_001"].inventory = {}
    campaign.items = {
        first.stack_id: first,
        second.stack_id: second,
    }

    with pytest.raises(ValueError, match="cycle"):
        repo.create_campaign(campaign)


def test_pure_item_read_helpers_ignore_legacy_actor_inventory_when_items_exist() -> None:
    campaign = _base_campaign("camp_items_pure_reads")
    campaign.actors["pc_001"].inventory = {"legacy_token": 99}
    torch_stack = create_runtime_item_stack(
        definition_id="torch",
        quantity=2,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        stack_id_salt="test_pure_reads:pc_001:torch",
    )
    campaign.items = {torch_stack.stack_id: torch_stack}

    assert derive_actor_inventory_from_items_only(campaign, "pc_001") == {"torch": 2}
    assert derive_all_actor_inventories_from_items_only(campaign) == {
        "pc_001": {"torch": 2}
    }
    assert get_actor_item_quantity_from_items_only(campaign, "pc_001", "torch") == 2
    assert get_actor_item_quantity_from_items_only(campaign, "pc_001", "legacy_token") == 0


def test_default_bootstrap_moves_portable_container_into_campaign_items(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)

    campaign_id = service.create_campaign(
        world_id="world_regular_phase1",
        map_id="map_001",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )
    campaign = repo.get_campaign(campaign_id)

    assert sorted(campaign.entities.keys()) == ["door_01", "npc_guide_01"]
    assert [stack.definition_id for stack in campaign.items.values()] == ["crate_01"]
    only_stack = next(iter(campaign.items.values()))
    assert only_stack.parent_type == "area"
    assert only_stack.parent_id == "area_001"
    assert only_stack.is_container is True
    assert only_stack.stackable is False
