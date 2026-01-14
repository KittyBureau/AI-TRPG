from __future__ import annotations

from typing import Iterable

from backend.domain.models import Campaign


def sync_state_positions(campaign: Campaign) -> None:
    if campaign.positions:
        campaign.state.positions_parent = dict(campaign.positions)
    elif campaign.state.positions_parent:
        campaign.positions = dict(campaign.state.positions_parent)
    elif campaign.state.positions:
        campaign.positions = dict(campaign.state.positions)
        campaign.state.positions_parent = dict(campaign.state.positions)

    if campaign.state.positions_parent:
        campaign.state.positions = dict(campaign.state.positions_parent)


def ensure_positions_child(
    campaign: Campaign, character_ids: Iterable[str]
) -> None:
    for character_id in character_ids:
        if character_id not in campaign.state.positions_child:
            campaign.state.positions_child[character_id] = None


def set_parent_position(
    campaign: Campaign, character_id: str, area_id: str
) -> None:
    campaign.positions[character_id] = area_id
    campaign.state.positions_parent[character_id] = area_id
    campaign.state.positions[character_id] = area_id
