from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.domain.models import (
    ActorState,
    AppliedAction,
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


class _NarrativeOnlyLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "The corridor is quiet.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


class _MixedToolLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_inventory_ok",
                    "tool": "inventory_add",
                    "args": {
                        "item_id": "torch",
                        "quantity": 1,
                        "source_entity_id": "torch_cache",
                    },
                },
                {
                    "id": "call_move_invalid",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_001"},
                },
            ],
        }


class _NarrativeAndToolSuccessLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "Existing narration.",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_inventory_ok",
                    "tool": "inventory_add",
                    "args": {
                        "item_id": "torch",
                        "quantity": 1,
                        "source_entity_id": "torch_cache",
                    },
                }
            ],
        }


class _FailedToolOnlyLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_move_invalid",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_001"},
                }
            ],
        }


class _ConflictMoveLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_move_conflict",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_002"},
                }
            ],
        }


def _create_campaign(
    tmp_path: Path,
    campaign_id: str,
    *,
    trace_enabled: bool = False,
) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Freeze the contract.", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="Start room.",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002",
                    name="Hall",
                    description="A narrow hall.",
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
        entities={
            "torch_cache": Entity(
                id="torch_cache",
                kind="object",
                label="Torch Cache",
                tags=["loot_source"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "search"],
                state={
                    "inventory_item_id": "torch",
                    "inventory_quantity": 1,
                    "inventory_granted": False,
                },
                props={},
            )
        },
    )
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = trace_enabled
    repo.create_campaign(campaign)


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    llm_class: type,
) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", llm_class)
    return TestClient(create_app())


def _assert_stable_top_level_keys(
    payload: Dict[str, Any], *, expect_debug: bool
) -> None:
    expected = {
        "effective_actor_id",
        "narrative_text",
        "dialog_type",
        "tool_calls",
        "applied_actions",
        "tool_feedback",
        "conflict_report",
        "state_summary",
    }
    if expect_debug:
        expected.add("debug")
    assert set(payload.keys()) == expected


def _assert_state_summary_contract(summary: Dict[str, Any]) -> None:
    for key in (
        "active_actor_id",
        "positions",
        "positions_parent",
        "positions_child",
        "hp",
        "character_states",
        "inventories",
        "objective",
        "active_area_id",
        "active_area_name",
        "active_area_description",
        "active_actor_inventory",
    ):
        assert key in summary


def test_chat_turn_narrative_response_contract_and_turn_log_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_narrative")
    client = _client(tmp_path, monkeypatch, _NarrativeOnlyLLM)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_narrative", "user_input": "Look around."},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_stable_top_level_keys(payload, expect_debug=False)
    assert payload["effective_actor_id"] == "pc_001"
    assert payload["tool_calls"] == []
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"] is None
    assert payload["conflict_report"] is None
    _assert_state_summary_contract(payload["state_summary"])

    turn_log_path = (
        tmp_path / "storage" / "campaigns" / "camp_contract_narrative" / "turn_log.jsonl"
    )
    rows = [
        json.loads(line)
        for line in turn_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert set(row.keys()) == {
        "turn_id",
        "timestamp",
        "user_input",
        "dialog_type",
        "dialog_type_source",
        "settings_revision",
        "assistant_text",
        "assistant_structured",
        "applied_actions",
        "tool_feedback",
        "conflict_report",
        "state_summary",
    }
    assert row["assistant_structured"]["tool_calls"] == []
    assert row["applied_actions"] == []
    assert row["tool_feedback"] is None
    assert row["conflict_report"] is None
    _assert_state_summary_contract(row["state_summary"])


def test_chat_turn_tool_response_contract_keeps_applied_actions_and_tool_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_tool")
    client = _client(tmp_path, monkeypatch, _MixedToolLLM)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_tool", "user_input": "Do the thing."},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_stable_top_level_keys(payload, expect_debug=False)
    assert len(payload["tool_calls"]) == 2
    assert len(payload["applied_actions"]) == 1
    assert payload["applied_actions"][0]["tool"] == "inventory_add"
    assert payload["applied_actions"][0]["result"] == {
        "actor_id": "pc_001",
        "item_id": "torch",
        "quantity_added": 1,
        "new_quantity": 1,
    }
    failed = payload["tool_feedback"]["failed_calls"]
    assert failed == [
        {
            "id": "call_move_invalid",
            "tool": "move",
            "status": "error",
            "reason": "invalid_args",
        }
    ]
    assert payload["conflict_report"] is None
    assert payload["state_summary"]["active_actor_inventory"] == {"torch": 1}
    assert payload["state_summary"]["inventories"] == {"pc_001": {"torch": 1}}
    assert payload["narrative_text"] == "The action was performed."


def test_chat_turn_keeps_existing_narrative_when_tool_success_also_occurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_tool_with_text")
    client = _client(tmp_path, monkeypatch, _NarrativeAndToolSuccessLLM)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_tool_with_text", "user_input": "Do the thing."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["applied_actions"]) == 1
    assert payload["applied_actions"][0]["tool"] == "inventory_add"
    assert payload["narrative_text"] == "Existing narration."


def test_chat_turn_failed_tool_only_keeps_empty_narrative_without_success_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_failed_tool_only")
    client = _client(tmp_path, monkeypatch, _FailedToolOnlyLLM)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_failed_tool_only", "user_input": "Move nowhere."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"]["failed_calls"] == [
        {
            "id": "call_move_invalid",
            "tool": "move",
            "status": "error",
            "reason": "invalid_args",
        }
    ]
    assert payload["narrative_text"] == ""


def test_chat_turn_conflict_response_contract_is_stable_and_not_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_conflict")
    client = _client(tmp_path, monkeypatch, _ConflictMoveLLM)

    def _conflicting_execute_tool_calls(*args, **kwargs):
        return (
            [
                AppliedAction(
                    tool="move",
                    args={"actor_id": "pc_001", "to_area_id": "area_002"},
                    result={"from_area_id": "area_001", "to_area_id": "area_002"},
                    timestamp="2026-03-06T00:00:00+00:00",
                )
            ],
            None,
        )

    monkeypatch.setattr(
        turn_service_module, "execute_tool_calls", _conflicting_execute_tool_calls
    )

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_conflict", "user_input": "Move now."},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_stable_top_level_keys(payload, expect_debug=False)
    assert payload["narrative_text"] == ""
    assert payload["tool_calls"] == []
    assert payload["applied_actions"] == []
    assert payload["tool_feedback"] is None
    assert isinstance(payload["conflict_report"], dict)
    assert payload["conflict_report"]["retries"] == 2
    assert isinstance(payload["conflict_report"]["conflicts"], list)
    assert payload["conflict_report"]["conflicts"]
    first = payload["conflict_report"]["conflicts"][0]
    assert first["type"] == "tool_result_mismatch"
    assert first["field"] == "move"
    _assert_state_summary_contract(payload["state_summary"])

    turn_log_path = (
        tmp_path / "storage" / "campaigns" / "camp_contract_conflict" / "turn_log.jsonl"
    )
    assert not turn_log_path.exists()


def test_chat_turn_trace_on_keeps_debug_resources_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_contract_trace", trace_enabled=True)
    client = _client(tmp_path, monkeypatch, _NarrativeOnlyLLM)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_contract_trace", "user_input": "Look around."},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_stable_top_level_keys(payload, expect_debug=True)
    debug = payload["debug"]
    assert isinstance(debug, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    for key in (
        "prompts",
        "flows",
        "schemas",
        "templates",
        "policies",
        "template_usage",
    ):
        assert key in resources
        assert isinstance(resources[key], list)
