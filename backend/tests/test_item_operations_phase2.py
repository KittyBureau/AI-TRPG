from __future__ import annotations

import pytest

from backend.app.item_operations import move_stack_quantity, split_stack
from backend.app.item_runtime import create_runtime_item_stack
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


def _base_campaign(campaign_id: str = "camp_item_ops_phase2") -> Campaign:
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
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Side",
                    description="Side area",
                    reachable_area_ids=[],
                ),
            },
            connections=[],
        ),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            )
        },
    )


def _stack(
    *,
    definition_id: str = "torch",
    quantity: int = 5,
    parent_type: str = "actor",
    parent_id: str = "pc_001",
    metadata: dict[str, object] | None = None,
    stackable: bool = True,
    label: str | None = None,
    salt: str = "default",
):
    return create_runtime_item_stack(
        definition_id=definition_id,
        quantity=quantity,
        parent_type=parent_type,
        parent_id=parent_id,
        metadata=metadata,
        label=label or definition_id,
        stackable=stackable,
        is_container=False,
        stack_id_salt=salt,
    )


def _assert_no_empty_stacks(campaign: Campaign) -> None:
    assert all(stack.quantity > 0 for stack in campaign.items.values())


def test_split_stack_partial_success_creates_distinct_stack() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=5, salt="split_source")
    campaign.items = {source.stack_id: source}

    created = split_stack(campaign, stack_id=source.stack_id, quantity=2)

    assert created.stack_id != source.stack_id
    assert created.quantity == 2
    assert created.parent_type == "actor"
    assert created.parent_id == "pc_001"
    assert campaign.items[source.stack_id].quantity == 3
    assert campaign.actors["pc_001"].inventory == {"torch": 5}
    _assert_no_empty_stacks(campaign)


@pytest.mark.parametrize("quantity", [0, -1, 6])
def test_split_stack_rejects_invalid_quantities(quantity: int) -> None:
    campaign = _base_campaign()
    source = _stack(quantity=5, salt=f"split_invalid_{quantity}")
    campaign.items = {source.stack_id: source}

    with pytest.raises(ValueError):
        split_stack(campaign, stack_id=source.stack_id, quantity=quantity)

    assert list(campaign.items.keys()) == [source.stack_id]
    assert campaign.items[source.stack_id].quantity == 5
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_full_move_reuses_existing_stack() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=4, salt="full_move")
    campaign.items = {source.stack_id: source}

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=4,
        allow_merge=False,
    )

    assert moved.stack_id == source.stack_id
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_001"
    assert sorted(campaign.items.keys()) == [source.stack_id]
    assert campaign.actors["pc_001"].inventory == {}
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_partial_without_merge_creates_destination_stack() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=5, salt="partial_move_no_merge")
    campaign.items = {source.stack_id: source}

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=2,
        allow_merge=False,
    )

    assert moved.stack_id != source.stack_id
    assert moved.quantity == 2
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_001"
    assert campaign.items[source.stack_id].quantity == 3
    assert campaign.actors["pc_001"].inventory == {"torch": 3}
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_partial_with_merge_absorbs_into_destination_stack() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=5, salt="partial_merge_source")
    destination = _stack(
        quantity=3,
        parent_type="area",
        parent_id="area_001",
        salt="partial_merge_destination",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    merged = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=2,
        allow_merge=True,
    )

    assert merged.stack_id == destination.stack_id
    assert campaign.items[destination.stack_id].quantity == 5
    assert campaign.items[source.stack_id].quantity == 3
    assert len(campaign.items) == 2
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_full_with_merge_removes_source_stack() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=2, salt="full_merge_source")
    destination = _stack(
        quantity=3,
        parent_type="area",
        parent_id="area_001",
        salt="full_merge_destination",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    merged = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=2,
        allow_merge=True,
    )

    assert merged.stack_id == destination.stack_id
    assert destination.stack_id in campaign.items
    assert source.stack_id not in campaign.items
    assert campaign.items[destination.stack_id].quantity == 5
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_does_not_merge_when_metadata_differs() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=2, metadata={"quality": "fine"}, salt="metadata_source")
    destination = _stack(
        quantity=3,
        parent_type="area",
        parent_id="area_001",
        metadata={"quality": "plain"},
        salt="metadata_destination",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=2,
        allow_merge=True,
    )

    assert moved.stack_id == source.stack_id
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_001"
    assert campaign.items[destination.stack_id].quantity == 3
    assert len(campaign.items) == 2
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_does_not_merge_non_stackable_items() -> None:
    campaign = _base_campaign()
    source = _stack(
        definition_id="badge",
        quantity=1,
        stackable=False,
        label="Badge",
        salt="non_stackable_source",
    )
    destination = _stack(
        definition_id="badge",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        stackable=False,
        label="Badge",
        salt="non_stackable_destination",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=1,
        allow_merge=True,
    )

    assert moved.stack_id == source.stack_id
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_001"
    assert len(campaign.items) == 2
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_only_merges_in_requested_destination() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=2, salt="different_destination_source")
    destination = _stack(
        quantity=3,
        parent_type="area",
        parent_id="area_001",
        salt="different_destination_target",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_002",
        quantity=2,
        allow_merge=True,
    )

    assert moved.stack_id == source.stack_id
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_002"
    assert campaign.items[destination.stack_id].quantity == 3
    assert len(campaign.items) == 2
    _assert_no_empty_stacks(campaign)


def test_move_stack_quantity_respects_allow_merge_false() -> None:
    campaign = _base_campaign()
    source = _stack(quantity=2, salt="allow_merge_false_source")
    destination = _stack(
        quantity=3,
        parent_type="area",
        parent_id="area_001",
        salt="allow_merge_false_destination",
    )
    campaign.items = {
        source.stack_id: source,
        destination.stack_id: destination,
    }

    moved = move_stack_quantity(
        campaign,
        stack_id=source.stack_id,
        parent_type="area",
        parent_id="area_001",
        quantity=2,
        allow_merge=False,
    )

    assert moved.stack_id == source.stack_id
    assert moved.parent_type == "area"
    assert moved.parent_id == "area_001"
    assert campaign.items[destination.stack_id].quantity == 3
    assert len(campaign.items) == 2
    _assert_no_empty_stacks(campaign)
