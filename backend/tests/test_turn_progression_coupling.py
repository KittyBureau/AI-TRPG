from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

import backend.app.turn_service as turn_service_module
from backend.app.turn_service import TurnService
from backend.app.world_presets import DEV_KEY_GATE_SCENARIO_WORLD_ID
from backend.infra.file_repo import FileRepo


class _ScenarioCouplingLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        if token == "TALK_HINT_THREAT":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_talk_hint_threat",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": "hint_source_001",
                            "params": {"tone": "threatening"},
                        },
                    }
                ],
            }
        if token == "MOVE_TO_CLUE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_clue",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_clue"},
                    }
                ],
            }
        if token == "SEARCH_CLUE_HOSTILE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_search_clue_hostile",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": "clue_source_001",
                            "params": {"approach": "violent"},
                        },
                    }
                ],
            }
        return {
            "assistant_text": "No action.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _make_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TurnService, FileRepo]:
    monkeypatch.setattr(turn_service_module, "LLMClient", _ScenarioCouplingLLM)
    repo = FileRepo(tmp_path / "storage")
    return TurnService(repo), repo


def test_hostility_lock_on_noncritical_hint_npc_does_not_fail_progression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign_id = service.create_campaign(
        world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    first = service.submit_turn(campaign_id, "TALK_HINT_THREAT")
    assert first["applied_actions"][0]["result"]["ok"] is True
    assert first["state_summary"]["hostility"]["target_count"] == 1
    assert first["state_summary"]["hostility"]["outcome_count"] == 0

    second = service.submit_turn(campaign_id, "TALK_HINT_THREAT")
    assert second["applied_actions"][0]["result"]["ok"] is False
    assert second["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked_triggered",
        "message": "hostility threshold reached: hint_source_001",
    }
    assert second["state_summary"]["hostility"]["outcome_count"] == 1
    assert second["state_summary"]["hostility"]["outcomes"] == [
        {
            "outcome_id": "hostility_hint_source_001_interaction_locked",
            "type": "interaction_locked",
            "target_id": "hint_source_001",
            "scope_kind": "entity",
            "active": True,
        }
    ]

    campaign = repo.get_campaign(campaign_id)
    assert campaign.lifecycle.ended is False
    assert campaign.lifecycle.reason is None
    assert campaign.goal.status == "active"


def test_locking_critical_clue_source_triggers_progression_locked_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign_id = service.create_campaign(
        world_id=DEV_KEY_GATE_SCENARIO_WORLD_ID,
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    move = service.submit_turn(campaign_id, "MOVE_TO_CLUE")
    assert move["applied_actions"][0]["tool"] == "move"
    assert move["state_summary"]["active_area_id"] == "area_clue"

    hostile_search = service.submit_turn(campaign_id, "SEARCH_CLUE_HOSTILE")
    assert hostile_search["applied_actions"][0]["tool"] == "scene_action"
    assert hostile_search["applied_actions"][0]["result"]["ok"] is False
    assert hostile_search["applied_actions"][0]["result"]["error"] == {
        "code": "interaction_locked_triggered",
        "message": "hostility threshold reached: clue_source_001",
    }
    assert hostile_search["narrative_text"] == (
        "You can no longer make progress with clue_source_001."
    )
    assert hostile_search["applied_actions"][0]["result"]["hostility"] == {
        "target_id": "clue_source_001",
        "scope_kind": "entity",
        "score": 2,
        "threshold": 2,
        "interaction_locked": True,
        "last_category": "assaultive_intent",
        "triggered_outcome_ids": [
            "hostility_clue_source_001_interaction_locked",
            "hostility_clue_source_001_progression_locked",
        ],
        "delta": 2,
        "triggered_outcomes": [
            {
                "outcome_id": "hostility_clue_source_001_interaction_locked",
                "type": "interaction_locked",
                "target_id": "clue_source_001",
                "scope_kind": "entity",
                "active": True,
            },
            {
                "outcome_id": "hostility_clue_source_001_progression_locked",
                "type": "progression_locked",
                "target_id": "clue_source_001",
                "scope_kind": "entity",
                "active": True,
            },
        ],
    }
    assert hostile_search["state_summary"]["hostility"] == {
        "target_count": 1,
        "outcome_count": 2,
        "targets": [
            {
                "target_id": "clue_source_001",
                "scope_kind": "entity",
                "score": 2,
                "threshold": 2,
                "interaction_locked": True,
                "last_category": "assaultive_intent",
                "triggered_outcome_ids": [
                    "hostility_clue_source_001_interaction_locked",
                    "hostility_clue_source_001_progression_locked",
                ],
            }
        ],
        "outcomes": [
            {
                "outcome_id": "hostility_clue_source_001_interaction_locked",
                "type": "interaction_locked",
                "target_id": "clue_source_001",
                "scope_kind": "entity",
                "active": True,
            },
            {
                "outcome_id": "hostility_clue_source_001_progression_locked",
                "type": "progression_locked",
                "target_id": "clue_source_001",
                "scope_kind": "entity",
                "active": True,
            },
        ],
    }

    campaign = repo.get_campaign(campaign_id)
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "progression_locked"
    assert campaign.goal.status == "failed"
    assert campaign.entities["clue_source_001"].state["interaction_locked"] is True
    assert campaign.entities["clue_source_001"].state["blocked_verbs"] == ["search"]
    assert list(campaign.hostility.outcomes.keys()) == [
        "hostility_clue_source_001_interaction_locked",
        "hostility_clue_source_001_progression_locked",
    ]

    with pytest.raises(ValueError, match="campaign has ended: progression_locked"):
        service.submit_turn(campaign_id, "MOVE_TO_CLUE")
