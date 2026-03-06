from __future__ import annotations

from backend.app.turn_service import _restore_state, _snapshot_state
from backend.domain.character_access import CharacterState, create_character_facade
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


def test_snapshot_restore_reverts_actor_state_without_writing_legacy_mirrors() -> None:
    campaign = _make_campaign()
    facade = create_character_facade()

    snapshot = _snapshot_state(campaign)
    facade.set_state(
        campaign,
        "pc_001",
        CharacterState(position="area_002", hp=4, character_state="dying"),
    )

    _restore_state(campaign, snapshot)

    assert campaign.actors["pc_001"].position == "area_001"
    assert campaign.actors["pc_001"].hp == 10
    assert campaign.actors["pc_001"].character_state == "alive"
    assert campaign.positions == {}
    assert campaign.hp == {}
    assert campaign.character_states == {}
