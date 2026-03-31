from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

import backend.app.turn_service as turn_service_module
from backend.app.turn_service import TurnService
from backend.domain.models import (
    ActorState,
    Campaign,
    Entity,
    EntityLocation,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _HostilityLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        params: Dict[str, Any]
        if token == "TALK_THREAT":
            params = {"tone": "threatening"}
        elif token == "TALK_ASSAULT":
            params = {"approach": "violent"}
        elif token == "SEARCH_GUARD":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_search_guard",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": "guard_01",
                            "params": {},
                        },
                    }
                ],
            }
        else:
            params = {"tone": "calm"}
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": f"call_{token.lower()}",
                    "tool": "scene_action",
                    "args": {
                        "actor_id": "pc_001",
                        "action": "talk",
                        "target_id": "guard_01",
                        "params": params,
                    },
                }
            ],
        }


def _make_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TurnService, FileRepo]:
    monkeypatch.setattr(turn_service_module, "LLMClient", _HostilityLLM)
    repo = FileRepo(tmp_path / "storage")
    return TurnService(repo), repo


def _create_campaign(repo: FileRepo, campaign_id: str) -> None:
    repo.create_campaign(
        Campaign(
            id=campaign_id,
            selected=Selected(
                world_id="world_001",
                map_id="map_001",
                party_character_ids=["pc_001"],
                active_actor_id="pc_001",
            ),
            settings_snapshot=SettingsSnapshot(),
            goal=Goal(text="Keep the conversation open.", status="active"),
            milestone=Milestone(current="intro", last_advanced_turn=0),
            map=MapData(
                areas={
                    "area_001": MapArea(
                        id="area_001",
                        name="Checkpoint",
                        description="A guarded checkpoint.",
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
            entities={
                "guard_01": Entity(
                    id="guard_01",
                    kind="npc",
                    label="Wary Guard",
                    tags=["guard"],
                    loc=EntityLocation(type="area", id="area_001"),
                    verbs=["inspect", "talk"],
                    state={},
                    props={},
                )
            },
        )
    )


def _create_campaign_with_guard_props(
    repo: FileRepo,
    campaign_id: str,
    *,
    guard_props: Dict[str, Any],
) -> None:
    repo.create_campaign(
        Campaign(
            id=campaign_id,
            selected=Selected(
                world_id="world_001",
                map_id="map_001",
                party_character_ids=["pc_001"],
                active_actor_id="pc_001",
            ),
            settings_snapshot=SettingsSnapshot(),
            goal=Goal(text="Keep the conversation open.", status="active"),
            milestone=Milestone(current="intro", last_advanced_turn=0),
            map=MapData(
                areas={
                    "area_001": MapArea(
                        id="area_001",
                        name="Checkpoint",
                        description="A guarded checkpoint.",
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
            entities={
                "guard_01": Entity(
                    id="guard_01",
                    kind="npc",
                    label="Wary Guard",
                    tags=["guard"],
                    loc=EntityLocation(type="area", id="area_001"),
                    verbs=["inspect", "talk"],
                    state={},
                    props=dict(guard_props),
                )
            },
        )
    )


def test_turn_service_persists_hostility_and_structured_lockout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign(repo, "camp_hostility_turns")

    calm = service.submit_turn("camp_hostility_turns", "TALK_CALM")
    assert calm["applied_actions"][0]["tool"] == "scene_action"
    assert calm["applied_actions"][0]["result"]["ok"] is True
    assert "hostility" not in calm["applied_actions"][0]["result"]
    assert calm["narrative_text"] == "You talk to Wary Guard."
    assert calm["state_summary"]["hostility"] == {
        "target_count": 0,
        "outcome_count": 0,
        "targets": [],
        "outcomes": [],
    }

    first_threat = service.submit_turn("camp_hostility_turns", "TALK_THREAT")
    assert first_threat["applied_actions"][0]["result"]["ok"] is True
    assert first_threat["applied_actions"][0]["result"]["hostility"] == {
        "target_id": "guard_01",
        "scope_kind": "entity",
        "score": 1,
        "threshold": 2,
        "interaction_locked": False,
        "last_category": "verbal_aggression",
        "triggered_outcome_ids": [],
        "delta": 1,
    }
    assert first_threat["state_summary"]["hostility"] == {
        "target_count": 1,
        "outcome_count": 0,
        "targets": [
            {
                "target_id": "guard_01",
                "scope_kind": "entity",
                "score": 1,
                "threshold": 2,
                "interaction_locked": False,
                "last_category": "verbal_aggression",
                "triggered_outcome_ids": [],
            }
        ],
        "outcomes": [],
    }

    second_threat = service.submit_turn("camp_hostility_turns", "TALK_THREAT")
    assert second_threat["applied_actions"][0]["result"]["ok"] is False
    assert second_threat["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked_triggered",
        "message": "hostility threshold reached: guard_01",
    }
    assert second_threat["narrative_text"] == (
        "Wary Guard refuses to continue interacting with you."
    )
    assert second_threat["state_summary"]["hostility"] == {
        "target_count": 1,
        "outcome_count": 1,
        "targets": [
            {
                "target_id": "guard_01",
                "scope_kind": "entity",
                "score": 2,
                "threshold": 2,
                "interaction_locked": True,
                "last_category": "verbal_aggression",
                "triggered_outcome_ids": ["hostility_guard_01_interaction_locked"],
            }
        ],
        "outcomes": [
            {
                "outcome_id": "hostility_guard_01_interaction_locked",
                "type": "interaction_locked",
                "target_id": "guard_01",
                "scope_kind": "entity",
                "active": True,
            }
        ],
    }

    reloaded = repo.get_campaign("camp_hostility_turns")
    assert reloaded is not None
    assert reloaded.hostility.targets["guard_01"].score == 2
    assert reloaded.hostility.targets["guard_01"].interaction_locked is True
    assert reloaded.hostility.targets["guard_01"].triggered_outcome_ids == [
        "hostility_guard_01_interaction_locked"
    ]
    assert list(reloaded.hostility.outcomes.keys()) == [
        "hostility_guard_01_interaction_locked"
    ]
    assert reloaded.entities["guard_01"].state["interaction_locked"] is True
    assert reloaded.entities["guard_01"].state["blocked_verbs"] == ["talk"]

    after_lock = service.submit_turn("camp_hostility_turns", "TALK_CALM")
    assert after_lock["applied_actions"][0]["result"]["ok"] is False
    assert after_lock["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked",
        "message": "interaction locked: guard_01",
    }
    assert after_lock["applied_actions"][0]["result"]["hostility"] == {
        "target_id": "guard_01",
        "scope_kind": "entity",
        "score": 2,
        "threshold": 2,
        "interaction_locked": True,
        "last_category": "verbal_aggression",
        "triggered_outcome_ids": ["hostility_guard_01_interaction_locked"],
        "triggered_outcomes": [
            {
                "outcome_id": "hostility_guard_01_interaction_locked",
                "type": "interaction_locked",
                "target_id": "guard_01",
                "scope_kind": "entity",
                "active": True,
            }
        ],
    }
    assert after_lock["narrative_text"] == (
        "Wary Guard refuses to continue interacting with you."
    )
    assert after_lock["state_summary"]["hostility"]["outcome_count"] == 1

    reloaded_again = repo.get_campaign("camp_hostility_turns")
    assert reloaded_again is not None
    assert reloaded_again.hostility.targets["guard_01"].score == 2
    assert list(reloaded_again.hostility.outcomes.keys()) == [
        "hostility_guard_01_interaction_locked"
    ]


def test_turn_service_assaultive_talk_triggers_combat_resolution_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign(repo, "camp_hostility_combat")

    calm = service.submit_turn("camp_hostility_combat", "TALK_CALM")
    assert calm["applied_actions"][0]["result"]["ok"] is True
    assert calm["state_summary"]["hostility"]["outcome_count"] == 0

    assault = service.submit_turn("camp_hostility_combat", "TALK_ASSAULT")
    assert assault["applied_actions"][0]["result"]["ok"] is False
    assert assault["applied_actions"][0]["result"]["error"] == {
        "code": "combat_triggered",
        "message": "combat triggered: guard_01",
    }
    assert assault["applied_actions"][0]["result"]["hostility"] == {
        "target_id": "guard_01",
        "scope_kind": "entity",
        "score": 2,
        "threshold": 2,
        "interaction_locked": True,
        "last_category": "assaultive_intent",
        "triggered_outcome_ids": ["hostility_guard_01_combat_resolved"],
        "delta": 2,
        "triggered_outcomes": [
            {
                "outcome_id": "hostility_guard_01_combat_resolved",
                "type": "combat_resolved",
                "target_id": "guard_01",
                "scope_kind": "entity",
                "active": True,
                "resolution": "player_repelled",
            }
        ],
    }
    assert assault["state_summary"]["hostility"] == {
        "target_count": 1,
        "outcome_count": 1,
        "targets": [
            {
                "target_id": "guard_01",
                "scope_kind": "entity",
                "score": 2,
                "threshold": 2,
                "interaction_locked": True,
                "last_category": "assaultive_intent",
                "triggered_outcome_ids": ["hostility_guard_01_combat_resolved"],
            }
        ],
        "outcomes": [
            {
                "outcome_id": "hostility_guard_01_combat_resolved",
                "type": "combat_resolved",
                "target_id": "guard_01",
                "scope_kind": "entity",
                "active": True,
                "resolution": "player_repelled",
            }
        ],
    }

    reloaded = repo.get_campaign("camp_hostility_combat")
    assert reloaded is not None
    assert reloaded.hostility.targets["guard_01"].score == 2
    assert reloaded.hostility.targets["guard_01"].interaction_locked is True
    assert reloaded.hostility.targets["guard_01"].triggered_outcome_ids == [
        "hostility_guard_01_combat_resolved"
    ]
    assert list(reloaded.hostility.outcomes.keys()) == [
        "hostility_guard_01_combat_resolved"
    ]
    assert reloaded.entities["guard_01"].state["interaction_locked"] is True
    assert reloaded.entities["guard_01"].state["blocked_verbs"] == ["talk"]
    assert reloaded.entities["guard_01"].state["combat_resolution"] == "player_repelled"

    after_lock = service.submit_turn("camp_hostility_combat", "TALK_CALM")
    assert after_lock["applied_actions"][0]["result"]["ok"] is False
    assert after_lock["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked",
        "message": "interaction locked: guard_01",
    }
    assert after_lock["state_summary"]["hostility"]["outcome_count"] == 1

    reloaded_again = repo.get_campaign("camp_hostility_combat")
    assert reloaded_again is not None
    assert list(reloaded_again.hostility.outcomes.keys()) == [
        "hostility_guard_01_combat_resolved"
    ]


def test_turn_service_assaultive_talk_can_persist_npc_disabled_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign_with_guard_props(
        repo,
        "camp_hostility_combat_disabled",
        guard_props={"combat_resolution": "npc_disabled"},
    )

    assault = service.submit_turn("camp_hostility_combat_disabled", "TALK_ASSAULT")
    assert assault["applied_actions"][0]["result"]["ok"] is False
    assert assault["applied_actions"][0]["result"]["error"] == {
        "code": "combat_triggered",
        "message": "combat triggered: guard_01",
    }
    assert assault["applied_actions"][0]["result"]["hostility"]["triggered_outcomes"] == [
        {
            "outcome_id": "hostility_guard_01_combat_resolved",
            "type": "combat_resolved",
            "target_id": "guard_01",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]
    assert assault["state_summary"]["hostility"]["outcomes"] == [
        {
            "outcome_id": "hostility_guard_01_combat_resolved",
            "type": "combat_resolved",
            "target_id": "guard_01",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]

    reloaded = repo.get_campaign("camp_hostility_combat_disabled")
    assert reloaded is not None
    assert reloaded.entities["guard_01"].state["interaction_locked"] is True
    assert reloaded.entities["guard_01"].state["disabled"] is True
    assert reloaded.entities["guard_01"].state["combat_resolution"] == "npc_disabled"
    assert sorted(reloaded.entities["guard_01"].state["blocked_verbs"]) == [
        "inspect",
        "talk",
    ]
    assert reloaded.hostility.targets["guard_01"].triggered_outcome_ids == [
        "hostility_guard_01_combat_resolved"
    ]
    assert list(reloaded.hostility.outcomes.keys()) == [
        "hostility_guard_01_combat_resolved"
    ]

    after_lock = service.submit_turn("camp_hostility_combat_disabled", "TALK_CALM")
    assert after_lock["applied_actions"][0]["result"]["ok"] is False
    assert after_lock["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked",
        "message": "interaction locked: guard_01",
    }
    assert after_lock["state_summary"]["hostility"]["outcomes"] == [
        {
            "outcome_id": "hostility_guard_01_combat_resolved",
            "type": "combat_resolved",
            "target_id": "guard_01",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]


def test_turn_service_npc_disabled_can_enable_later_search_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign_with_guard_props(
        repo,
        "camp_hostility_combat_search_after_disable",
        guard_props={
            "combat_resolution": "npc_disabled",
            "combat_reveal_item_id": "guard_pass",
            "combat_reveal_item_label": "Guard Pass",
        },
    )

    assault = service.submit_turn(
        "camp_hostility_combat_search_after_disable",
        "TALK_ASSAULT",
    )
    assert assault["applied_actions"][0]["result"]["ok"] is False
    assert assault["applied_actions"][0]["result"]["error"]["code"] == "combat_triggered"

    search = service.submit_turn(
        "camp_hostility_combat_search_after_disable",
        "SEARCH_GUARD",
    )
    assert search["applied_actions"][0]["tool"] == "scene_action"
    assert search["applied_actions"][0]["result"]["ok"] is True
    assert search["applied_actions"][0]["result"]["narrative"] == (
        "You search Wary Guard and find Guard Pass."
    )
    assert search["state_summary"]["hostility"]["outcomes"] == [
        {
            "outcome_id": "hostility_guard_01_combat_resolved",
            "type": "combat_resolved",
            "target_id": "guard_01",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]

    reloaded = repo.get_campaign("camp_hostility_combat_search_after_disable")
    assert reloaded is not None
    assert reloaded.entities["guard_01"].state["disabled"] is True
    assert reloaded.entities["guard_01"].state["search_generated_loot"] is True
    assert any(
        stack.definition_id == "guard_pass" and stack.parent_id == "area_001"
        for stack in reloaded.items.values()
    )


def test_turn_service_npc_disabled_search_aftermath_hook_can_enable_later_search_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign_with_guard_props(
        repo,
        "camp_hostility_combat_search_after_hook",
        guard_props={
            "combat_resolution": "npc_disabled",
            "combat_aftermath_hook": {
                "kind": "search_loot",
                "item_id": "guard_badge",
                "item_label": "Guard Badge",
            },
        },
    )

    assault = service.submit_turn(
        "camp_hostility_combat_search_after_hook",
        "TALK_ASSAULT",
    )
    assert assault["applied_actions"][0]["result"]["ok"] is False
    assert assault["applied_actions"][0]["result"]["error"]["code"] == "combat_triggered"

    search = service.submit_turn(
        "camp_hostility_combat_search_after_hook",
        "SEARCH_GUARD",
    )
    assert search["applied_actions"][0]["tool"] == "scene_action"
    assert search["applied_actions"][0]["result"]["ok"] is True
    assert search["applied_actions"][0]["result"]["narrative"] == (
        "You search Wary Guard and find Guard Badge."
    )
    assert search["state_summary"]["hostility"]["outcomes"] == [
        {
            "outcome_id": "hostility_guard_01_combat_resolved",
            "type": "combat_resolved",
            "target_id": "guard_01",
            "scope_kind": "entity",
            "active": True,
            "resolution": "npc_disabled",
        }
    ]

    reloaded = repo.get_campaign("camp_hostility_combat_search_after_hook")
    assert reloaded is not None
    assert reloaded.entities["guard_01"].state["disabled"] is True
    assert reloaded.entities["guard_01"].state["search_generated_loot"] is True
    assert any(
        stack.definition_id == "guard_badge" and stack.parent_id == "area_001"
        for stack in reloaded.items.values()
    )
