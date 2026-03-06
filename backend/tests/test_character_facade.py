from __future__ import annotations

from backend.domain.character_access import (
    CharacterState,
    create_character_facade,
)
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    Milestone,
    Selected,
    SettingsSnapshot,
)


def _make_campaign() -> Campaign:
    return Campaign(
        id="camp_test",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )


def test_set_state_updates_actor_without_writing_legacy_mirrors() -> None:
    campaign = _make_campaign()
    facade = create_character_facade()

    facade.set_state(
        campaign,
        "pc_001",
        CharacterState(position="area_002", hp=7, character_state="dying"),
    )

    state = facade.get_state(campaign, "pc_001")
    assert state.position == "area_002"
    assert state.hp == 7
    assert state.character_state == "dying"
    assert campaign.actors["pc_001"].position == "area_002"
    assert campaign.actors["pc_001"].hp == 7
    assert campaign.actors["pc_001"].character_state == "dying"
    assert campaign.positions == {}
    assert campaign.hp == {}
    assert campaign.character_states == {}
    assert campaign.state.positions == {}
    assert campaign.state.positions_parent == {}
    assert campaign.state.positions_child == {}


def test_get_state_reads_legacy_mirrors_without_rewriting_them() -> None:
    campaign = _make_campaign()
    campaign.positions["pc_001"] = "area_002"
    campaign.hp["pc_001"] = 7
    campaign.character_states["pc_001"] = "dying"
    campaign.state.positions["pc_001"] = "area_002"
    campaign.state.positions_parent["pc_001"] = "area_002"
    facade = create_character_facade()

    state = facade.get_state(campaign, "pc_001")

    assert state.position == "area_002"
    assert state.hp == 7
    assert state.character_state == "dying"
    assert campaign.actors["pc_001"].position == "area_002"
    assert campaign.actors["pc_001"].hp == 7
    assert campaign.actors["pc_001"].character_state == "dying"
    assert campaign.positions == {"pc_001": "area_002"}
    assert campaign.hp == {"pc_001": 7}
    assert campaign.character_states == {"pc_001": "dying"}


def test_get_view_uses_stub_fact_and_runtime_state() -> None:
    campaign = _make_campaign()
    campaign.actors["pc_001"].meta = {
        "name": "Ava",
        "role": "scout",
        "tags": ["party", "fast"],
        "attributes": {"agility": 3},
        "background": "Former outrider.",
        "appearance": "Light armor.",
        "personality_tags": ["calm"],
    }
    facade = create_character_facade()

    view = facade.get_view(campaign, "pc_001")
    assert view.character_id == "pc_001"
    assert view.name == "Ava"
    assert view.role == "scout"
    assert view.position == "area_001"
    assert view.hp == 10
    assert view.character_state == "alive"
    assert view.tags == ["party", "fast"]
    assert view.attributes == {"agility": 3}


def test_list_party_views_initializes_missing_party_actor() -> None:
    campaign = _make_campaign()
    campaign.selected.party_character_ids = ["pc_001", "pc_002"]
    facade = create_character_facade()

    views = facade.list_party_views(campaign)
    ids = [view.character_id for view in views]

    assert ids == ["pc_001", "pc_002"]
    assert campaign.actors["pc_002"].hp == 10
    assert campaign.actors["pc_002"].character_state == "alive"
