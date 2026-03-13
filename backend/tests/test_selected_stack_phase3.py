from __future__ import annotations

from backend.app.item_runtime import (
    create_runtime_item_stack,
    derive_actor_inventory_stack_ids_from_items_only,
    resolve_selected_stack,
)
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


def _build_campaign() -> tuple[Campaign, dict[str, str]]:
    torch_stack_a = create_runtime_item_stack(
        stack_id="stk_torch_0001aaaa",
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        props={"variant": "old"},
    )
    torch_stack_b = create_runtime_item_stack(
        stack_id="stk_torch_ffff0002",
        definition_id="torch",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="torch",
        props={"variant": "new"},
    )
    rope_stack = create_runtime_item_stack(
        stack_id="stk_rope_0101bbbb",
        definition_id="rope",
        quantity=1,
        parent_type="actor",
        parent_id="pc_001",
        label="rope",
    )
    area_stack = create_runtime_item_stack(
        stack_id="stk_medkit_0202cccc",
        definition_id="medkit",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="medkit",
    )
    campaign = Campaign(
        id="camp_selected_stack_phase3",
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
                inventory={},
                meta={},
            )
        },
        items={
            torch_stack_a.stack_id: torch_stack_a,
            torch_stack_b.stack_id: torch_stack_b,
            rope_stack.stack_id: rope_stack,
            area_stack.stack_id: area_stack,
        },
    )
    return campaign, {
        "torch_a": torch_stack_a.stack_id,
        "torch_b": torch_stack_b.stack_id,
        "rope": rope_stack.stack_id,
        "medkit": area_stack.stack_id,
    }


def test_derive_actor_inventory_stack_ids_lists_all_stacks_in_stable_order() -> None:
    campaign, stack_ids = _build_campaign()

    assert derive_actor_inventory_stack_ids_from_items_only(campaign, "pc_001") == {
        "rope": [stack_ids["rope"]],
        "torch": [stack_ids["torch_a"], stack_ids["torch_b"]],
    }


def test_resolve_selected_stack_falls_back_from_item_id_to_stable_first_stack() -> None:
    campaign, stack_ids = _build_campaign()

    selected_stack = resolve_selected_stack(
        campaign,
        "pc_001",
        selected_item_id="torch",
    )

    assert selected_stack is not None
    assert selected_stack.stack_id == stack_ids["torch_a"]


def test_resolve_selected_stack_prefers_explicit_stack_id_and_rejects_invalid_stack() -> None:
    campaign, stack_ids = _build_campaign()

    explicit = resolve_selected_stack(
        campaign,
        "pc_001",
        selected_stack_id=stack_ids["torch_b"],
        selected_item_id="rope",
    )
    invalid = resolve_selected_stack(
        campaign,
        "pc_001",
        selected_stack_id=stack_ids["medkit"],
        selected_item_id="torch",
    )

    assert explicit is not None
    assert explicit.stack_id == stack_ids["torch_b"]
    assert invalid is None
