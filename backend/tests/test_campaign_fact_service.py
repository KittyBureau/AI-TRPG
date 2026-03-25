from __future__ import annotations

import json
from pathlib import Path

from backend.app.campaign_fact_service import (
    CampaignFactService,
    build_fact_debug_context,
    build_fact_prompt_context,
    build_npc_memory_context,
    prune_campaign_facts,
)
from backend.domain.fact_models import CampaignFact
from backend.domain.models import ActorState, Campaign, Goal, Milestone, Selected
from backend.infra.file_repo import FileRepo


def _create_campaign(repo: FileRepo, campaign_id: str) -> Campaign:
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )
    repo.create_campaign(campaign)
    return campaign


def test_add_fact_persists_to_campaign_container(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    _create_campaign(repo, "camp_0001")
    service = CampaignFactService(repo)

    fact = service.add_fact(
        "camp_0001",
        {
            "fact_type": "route_hint",
            "summary": "A service route may bypass the locked door.",
            "source": {"kind": "llm", "ref_id": "turn_0007", "actor_id": "pc_001"},
            "authority": "uncertain",
            "reliability": "generated",
            "scope": {"kind": "area", "ref_id": "area_001"},
            "created_turn_index": 7,
            "metadata": {"tag": "test"},
        },
    )

    reloaded = repo.get_campaign("camp_0001")
    assert fact.fact_id in reloaded.facts
    stored = reloaded.facts[fact.fact_id]
    assert stored.fact_type == "route_hint"
    assert stored.authority == "uncertain"
    assert stored.reliability == "generated"
    assert stored.scope.kind == "area"
    assert stored.scope.ref_id == "area_001"
    assert stored.created_turn_index == 7
    assert stored.metadata == {"tag": "test"}


def test_old_campaign_without_facts_field_loads_cleanly(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _create_campaign(repo, "camp_0002")
    path = repo.campaigns_root / "camp_0002" / "campaign.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("facts", None)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    reloaded = repo.get_campaign(campaign.id)

    assert reloaded.facts == {}


def test_add_fact_dedupes_same_source_exact_match(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    _create_campaign(repo, "camp_0003")
    service = CampaignFactService(repo)
    payload = {
        "fact_type": "scene_observation",
        "summary": "The crate has already been searched.",
        "source": {"kind": "tool", "ref_id": "search:crate_01", "actor_id": "pc_001"},
        "authority": "authoritative",
        "reliability": "confirmed",
        "scope": {"kind": "entity", "ref_id": "crate_01"},
    }

    first = service.add_fact("camp_0003", payload)
    second = service.add_fact("camp_0003", payload)

    assert first.fact_id == second.fact_id
    assert [fact.fact_id for fact in service.list_facts("camp_0003")] == [first.fact_id]


def test_fact_prompt_context_separates_authoritative_and_uncertain() -> None:
    campaign = Campaign(
        id="camp_ctx",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts={
            "fact_area_authoritative": {
                "fact_id": "fact_area_authoritative",
                "fact_type": "route_hint",
                "summary": "The archive door is locked from this side.",
                "source": {"kind": "system", "ref_id": "preset"},
                "authority": "authoritative",
                "reliability": "confirmed",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "created_turn_index": 3,
                "metadata": {},
            },
            "fact_area_uncertain": {
                "fact_id": "fact_area_uncertain",
                "fact_type": "route_hint",
                "summary": "There may be another way through the service route.",
                "source": {"kind": "llm", "ref_id": "turn_0003", "actor_id": "pc_001"},
                "authority": "uncertain",
                "reliability": "generated",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "created_turn_index": 3,
                "metadata": {},
            },
            "fact_actor_uncertain": {
                "fact_id": "fact_actor_uncertain",
                "fact_type": "npc_read",
                "summary": "The guard sounded nervous during questioning.",
                "source": {"kind": "llm", "ref_id": "turn_0004", "actor_id": "pc_001"},
                "authority": "uncertain",
                "reliability": "reported",
                "scope": {"kind": "actor", "ref_id": "pc_001"},
                "created_turn_index": 4,
                "metadata": {},
            },
        },
    )

    prompt_context = build_fact_prompt_context(campaign, "pc_001")
    debug_context = build_fact_debug_context(campaign, "pc_001")

    assert prompt_context["slot"] == "campaign_facts_v1"
    assert [fact["fact_id"] for fact in prompt_context["authoritative"]] == [
        "fact_area_authoritative"
    ]
    assert [fact["fact_id"] for fact in prompt_context["uncertain"]] == [
        "fact_actor_uncertain"
    ]
    assert debug_context["suppressed_uncertain_ids"] == ["fact_area_uncertain"]


def test_prompt_context_hard_limits_selected_fact_count() -> None:
    facts = {
        f"fact_{index}": {
            "fact_id": f"fact_{index}",
            "fact_type": f"hint_{index}",
            "summary": f"Summary {index}",
            "source": {"kind": "llm", "ref_id": f"turn_{index:04d}"},
            "authority": "uncertain",
            "reliability": "generated",
            "scope": {"kind": "campaign"},
            "created_turn_index": index,
            "metadata": {},
        }
        for index in range(7)
    }
    campaign = Campaign(
        id="camp_limit",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts=facts,
    )

    prompt_context = build_fact_prompt_context(
        campaign,
        "pc_001",
        current_turn_index=8,
        max_items=5,
    )
    debug_context = build_fact_debug_context(
        campaign,
        "pc_001",
        current_turn_index=8,
        max_items=5,
    )

    assert len(prompt_context["authoritative"]) + len(prompt_context["uncertain"]) == 5
    assert debug_context["omitted_due_to_limit_ids"] == ["fact_1", "fact_0"]


def test_authoritative_fact_outranks_more_recent_uncertain_fact() -> None:
    campaign = Campaign(
        id="camp_priority_authority",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts={
            "fact_authoritative": {
                "fact_id": "fact_authoritative",
                "fact_type": "route_hint",
                "summary": "The door is definitely locked.",
                "source": {"kind": "system", "ref_id": "preset"},
                "authority": "authoritative",
                "reliability": "confirmed",
                "scope": {"kind": "campaign"},
                "created_turn_index": 1,
                "metadata": {},
            },
            "fact_uncertain_recent": {
                "fact_id": "fact_uncertain_recent",
                "fact_type": "route_hint_recent",
                "summary": "A hidden latch might exist nearby.",
                "source": {"kind": "llm", "ref_id": "turn_0009"},
                "authority": "uncertain",
                "reliability": "generated",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "created_turn_index": 9,
                "metadata": {},
            },
        },
    )

    prompt_context = build_fact_prompt_context(
        campaign,
        "pc_001",
        current_turn_index=10,
        max_items=1,
    )

    assert [fact["fact_id"] for fact in prompt_context["authoritative"]] == [
        "fact_authoritative"
    ]
    assert prompt_context["uncertain"] == []


def test_current_area_fact_outranks_other_area_fact() -> None:
    campaign = Campaign(
        id="camp_priority_area",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts={
            "fact_current_area": {
                "fact_id": "fact_current_area",
                "fact_type": "route_hint",
                "summary": "The current room smells of smoke.",
                "source": {"kind": "system", "ref_id": "preset"},
                "authority": "authoritative",
                "reliability": "confirmed",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "created_turn_index": 1,
                "metadata": {},
            },
            "fact_other_area_recent": {
                "fact_id": "fact_other_area_recent",
                "fact_type": "route_hint_other",
                "summary": "Another room has a flooded passage.",
                "source": {"kind": "system", "ref_id": "preset"},
                "authority": "authoritative",
                "reliability": "confirmed",
                "scope": {"kind": "area", "ref_id": "area_999"},
                "created_turn_index": 9,
                "metadata": {},
            },
        },
    )

    prompt_context = build_fact_prompt_context(
        campaign,
        "pc_001",
        current_turn_index=10,
        max_items=1,
    )

    assert [fact["fact_id"] for fact in prompt_context["authoritative"]] == [
        "fact_current_area"
    ]


def test_temporary_fact_expires_out_of_prompt_selection() -> None:
    campaign = Campaign(
        id="camp_expiry",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts={
            "fact_temp_expired": {
                "fact_id": "fact_temp_expired",
                "fact_type": "scene_read",
                "summary": "The dust looked freshly disturbed.",
                "source": {"kind": "llm", "ref_id": "turn_0002"},
                "authority": "uncertain",
                "reliability": "generated",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "lifecycle": "temporary",
                "expires_turn_index": 4,
                "created_turn_index": 2,
                "metadata": {},
            },
            "fact_persistent": {
                "fact_id": "fact_persistent",
                "fact_type": "route_hint",
                "summary": "The door remains locked.",
                "source": {"kind": "system", "ref_id": "preset"},
                "authority": "authoritative",
                "reliability": "confirmed",
                "scope": {"kind": "area", "ref_id": "area_001"},
                "created_turn_index": 1,
                "metadata": {},
            },
        },
    )

    prompt_context = build_fact_prompt_context(
        campaign,
        "pc_001",
        current_turn_index=6,
        max_items=5,
    )
    debug_context = build_fact_debug_context(
        campaign,
        "pc_001",
        current_turn_index=6,
        max_items=5,
    )

    assert [fact["fact_id"] for fact in prompt_context["authoritative"]] == [
        "fact_persistent"
    ]
    assert prompt_context["uncertain"] == []
    assert debug_context["expired_temporary_ids"] == ["fact_temp_expired"]


def test_pruning_removes_expired_and_low_priority_temporary_facts(tmp_path: Path) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = _create_campaign(repo, "camp_prune")
    campaign.facts = {
        "fact_persistent": CampaignFact.model_validate({
            "fact_id": "fact_persistent",
            "fact_type": "route_hint",
            "summary": "The locked gate is still relevant.",
            "source": {"kind": "system", "ref_id": "preset"},
            "authority": "authoritative",
            "reliability": "confirmed",
            "scope": {"kind": "campaign"},
            "created_turn_index": 1,
            "metadata": {},
        }),
        "fact_temp_expired": CampaignFact.model_validate({
            "fact_id": "fact_temp_expired",
            "fact_type": "scene_read",
            "summary": "A passing noise was heard earlier.",
            "source": {"kind": "llm", "ref_id": "turn_0002"},
            "authority": "uncertain",
            "reliability": "generated",
            "scope": {"kind": "area", "ref_id": "area_001"},
            "lifecycle": "temporary",
            "expires_turn_index": 3,
            "created_turn_index": 2,
            "metadata": {},
        }),
        "fact_temp_old": CampaignFact.model_validate({
            "fact_id": "fact_temp_old",
            "fact_type": "scene_read_old",
            "summary": "The shelves rattled once.",
            "source": {"kind": "llm", "ref_id": "turn_0003"},
            "authority": "uncertain",
            "reliability": "generated",
            "scope": {"kind": "campaign"},
            "lifecycle": "temporary",
            "expires_turn_index": 10,
            "created_turn_index": 3,
            "metadata": {},
        }),
        "fact_temp_new": CampaignFact.model_validate({
            "fact_id": "fact_temp_new",
            "fact_type": "scene_read_new",
            "summary": "The torch flickered just now.",
            "source": {"kind": "llm", "ref_id": "turn_0009"},
            "authority": "uncertain",
            "reliability": "generated",
            "scope": {"kind": "campaign"},
            "lifecycle": "temporary",
            "expires_turn_index": 12,
            "created_turn_index": 9,
            "metadata": {},
        }),
    }

    removed = prune_campaign_facts(campaign, current_turn_index=6, max_total=2)

    assert removed == ["fact_temp_expired", "fact_temp_old"]
    assert isinstance(campaign.facts, dict)
    assert sorted(campaign.facts.keys()) == ["fact_persistent", "fact_temp_new"]


def test_npc_memory_context_selects_only_target_npc_memories_and_caps_output() -> None:
    campaign = Campaign(
        id="camp_npc_memory_context",
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro"),
        actors={
            "pc_001": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
        },
        facts={
            "guide_memory_old": CampaignFact.model_validate(
                {
                    "fact_id": "guide_memory_old",
                    "fact_type": "npc_memory",
                    "summary": "Previous topic: old clue",
                    "source": {"kind": "system", "ref_id": "turn_0001", "actor_id": "pc_001"},
                    "authority": "uncertain",
                    "reliability": "generated",
                    "scope": {"kind": "npc", "ref_id": "guide_01"},
                    "lifecycle": "temporary",
                    "expires_turn_index": 8,
                    "created_turn_index": 1,
                    "metadata": {"npc_label": "Guide"},
                }
            ),
            "guide_memory_mid": CampaignFact.model_validate(
                {
                    "fact_id": "guide_memory_mid",
                    "fact_type": "npc_memory",
                    "summary": "Previous topic: hidden door",
                    "source": {"kind": "system", "ref_id": "turn_0002", "actor_id": "pc_001"},
                    "authority": "uncertain",
                    "reliability": "generated",
                    "scope": {"kind": "npc", "ref_id": "guide_01"},
                    "lifecycle": "temporary",
                    "expires_turn_index": 8,
                    "created_turn_index": 2,
                    "metadata": {"npc_label": "Guide"},
                }
            ),
            "guide_memory_new": CampaignFact.model_validate(
                {
                    "fact_id": "guide_memory_new",
                    "fact_type": "npc_memory",
                    "summary": "Previous topic: archive key",
                    "source": {"kind": "system", "ref_id": "turn_0003", "actor_id": "pc_001"},
                    "authority": "uncertain",
                    "reliability": "generated",
                    "scope": {"kind": "npc", "ref_id": "guide_01"},
                    "lifecycle": "temporary",
                    "expires_turn_index": 8,
                    "created_turn_index": 3,
                    "metadata": {"npc_label": "Guide"},
                }
            ),
            "guide_memory_latest": CampaignFact.model_validate(
                {
                    "fact_id": "guide_memory_latest",
                    "fact_type": "npc_memory",
                    "summary": "Previous topic: night watch",
                    "source": {"kind": "system", "ref_id": "turn_0004", "actor_id": "pc_001"},
                    "authority": "uncertain",
                    "reliability": "generated",
                    "scope": {"kind": "npc", "ref_id": "guide_01"},
                    "lifecycle": "temporary",
                    "expires_turn_index": 8,
                    "created_turn_index": 4,
                    "metadata": {"npc_label": "Guide"},
                }
            ),
            "guard_memory": CampaignFact.model_validate(
                {
                    "fact_id": "guard_memory",
                    "fact_type": "npc_memory",
                    "summary": "Previous topic: village gate",
                    "source": {"kind": "system", "ref_id": "turn_0005", "actor_id": "pc_001"},
                    "authority": "uncertain",
                    "reliability": "generated",
                    "scope": {"kind": "npc", "ref_id": "guard_01"},
                    "lifecycle": "temporary",
                    "expires_turn_index": 8,
                    "created_turn_index": 5,
                    "metadata": {"npc_label": "Guard"},
                }
            ),
        },
    )

    npc_memory = build_npc_memory_context(
        campaign,
        npc_id="guide_01",
        npc_label="Guide",
        current_turn_index=6,
        max_items=3,
    )

    assert npc_memory is not None
    assert npc_memory["npc_id"] == "guide_01"
    assert npc_memory["fact_ids"] == [
        "guide_memory_latest",
        "guide_memory_new",
        "guide_memory_mid",
    ]
    assert len(npc_memory["items"]) == 3
