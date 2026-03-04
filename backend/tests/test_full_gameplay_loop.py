from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app

WORLD_ID = "world_full_gameplay_v1"
SPAWN_CHARACTER_ID = "char_smoke_support"


class _StubFullGameplayLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        tool_calls: List[Dict[str, Any]] = []
        assistant_text = ""

        if token == "SMOKE_FULL_WORLD":
            tool_calls = [
                {
                    "id": "call_full_world",
                    "tool": "world_generate",
                    "args": {"world_id": WORLD_ID, "bind_to_campaign": True},
                }
            ]
        elif token == "SMOKE_FULL_MAP":
            tool_calls = [
                {
                    "id": "call_full_map",
                    "tool": "map_generate",
                    "args": {
                        "parent_area_id": "area_001",
                        "theme": "SmokeRoute",
                        "constraints": {"size": 2, "seed": "smoke-full"},
                    },
                }
            ]
        elif token == "SMOKE_FULL_SPAWN":
            tool_calls = [
                {
                    "id": "call_full_spawn",
                    "tool": "actor_spawn",
                    "args": {"character_id": SPAWN_CHARACTER_ID},
                }
            ]
        elif token == "SMOKE_FULL_OPTIONS":
            tool_calls = [
                {"id": "call_full_options", "tool": "move_options", "args": {}}
            ]
        elif token == "SMOKE_FULL_MOVE":
            tool_calls = [
                {
                    "id": "call_full_move",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_002"},
                }
            ]
        elif token == "SMOKE_FULL_CHAT":
            assistant_text = "The room settles. You hear only distant dripping water."
        else:
            assistant_text = "Unhandled smoke token."

        return {
            "assistant_text": assistant_text,
            "dialog_type": "scene_description",
            "tool_calls": tool_calls,
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubFullGameplayLLM)
    return TestClient(create_app())


def _field_line(path: Path, needle: str) -> int:
    if not path.exists():
        return 1
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return idx
    return 1


def _loc(step: str, field: str, path: Path, needle: str) -> str:
    return f"{step} -> {field} -> {path}:{_field_line(path, needle)}"


def test_full_gameplay_loop_persists_key_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    create_resp = client.post("/api/v1/campaign/create", json={})
    assert create_resp.status_code == 200
    campaign_id = create_resp.json()["campaign_id"]
    assert isinstance(campaign_id, str) and campaign_id

    step_plan = [
        ("SMOKE_FULL_WORLD", "world_generate"),
        ("SMOKE_FULL_MAP", "map_generate"),
        ("SMOKE_FULL_SPAWN", "actor_spawn"),
        ("SMOKE_FULL_OPTIONS", "move_options"),
        ("SMOKE_FULL_MOVE", "move"),
        ("SMOKE_FULL_CHAT", None),
    ]
    actions_by_tool: Dict[str, Dict[str, Any]] = {}

    for token, expected_tool in step_plan:
        turn_resp = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert turn_resp.status_code == 200, f"{token} status={turn_resp.status_code}"
        payload = turn_resp.json()
        applied_actions = payload["applied_actions"]

        if expected_tool is None:
            assert applied_actions == [], f"{token} -> applied_actions -> response"
            assert payload["tool_calls"] == [], f"{token} -> tool_calls -> response"
            assert payload["narrative_text"].strip(), f"{token} -> narrative_text -> response"
            continue

        assert len(applied_actions) == 1, f"{token} -> applied_actions[0] -> response"
        action = applied_actions[0]
        assert action["tool"] == expected_tool, (
            f"{token} -> applied_actions[0].tool -> response "
            f"(expected={expected_tool}, actual={action['tool']})"
        )
        actions_by_tool[expected_tool] = action

    world_action = actions_by_tool["world_generate"]
    map_action = actions_by_tool["map_generate"]
    spawn_action = actions_by_tool["actor_spawn"]
    move_options_action = actions_by_tool["move_options"]
    move_action = actions_by_tool["move"]

    world_result = world_action["result"]
    map_result = map_action["result"]
    spawn_result = spawn_action["result"]
    move_options_result = move_options_action["result"]
    move_result = move_action["result"]

    assert world_result["world_id"] == WORLD_ID
    assert world_result["bound_to_campaign"] is True
    created_area_ids = map_result["created_area_ids"]
    assert isinstance(created_area_ids, list) and created_area_ids
    spawned_actor_id = spawn_result["actor_id"]
    assert spawned_actor_id.startswith("actor_")
    options = move_options_result["options"]
    assert any(item.get("to_area_id") == "area_002" for item in options)
    assert move_result["to_area_id"] == "area_002"

    campaign_path = tmp_path / "storage" / "campaigns" / campaign_id / "campaign.json"
    world_path = tmp_path / "storage" / "worlds" / WORLD_ID / "world.json"
    turn_log_path = tmp_path / "storage" / "campaigns" / campaign_id / "turn_log.jsonl"

    assert campaign_path.exists(), f"{_loc('persistence', 'campaign.json', campaign_path, 'id')}"
    assert world_path.exists(), f"{_loc('persistence', 'world.json', world_path, 'world_id')}"
    assert turn_log_path.exists(), f"{_loc('persistence', 'turn_log.jsonl', turn_log_path, 'turn_id')}"

    campaign_obj = json.loads(campaign_path.read_text(encoding="utf-8"))
    world_obj = json.loads(world_path.read_text(encoding="utf-8"))
    turn_rows = [
        json.loads(line)
        for line in turn_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert campaign_obj["selected"]["world_id"] == WORLD_ID, _loc(
        "world_generate",
        "selected.world_id",
        campaign_path,
        '"world_id"',
    )
    for area_id in created_area_ids:
        assert area_id in campaign_obj["map"]["areas"], _loc(
            "map_generate",
            f"map.areas.{area_id}",
            campaign_path,
            area_id,
        )
    assert spawned_actor_id in campaign_obj["actors"], _loc(
        "actor_spawn",
        "actors.<spawned_actor_id>",
        campaign_path,
        spawned_actor_id,
    )
    assert spawned_actor_id in campaign_obj["selected"]["party_character_ids"], _loc(
        "actor_spawn",
        "selected.party_character_ids",
        campaign_path,
        '"party_character_ids"',
    )
    assert (
        campaign_obj["actors"][spawned_actor_id]["meta"]["character_id"]
        == SPAWN_CHARACTER_ID
    ), _loc(
        "actor_spawn",
        "actors.<spawned_actor_id>.meta.character_id",
        campaign_path,
        '"character_id"',
    )
    assert campaign_obj["actors"]["pc_001"]["position"] == "area_002", _loc(
        "move",
        "actors.pc_001.position",
        campaign_path,
        '"position"',
    )
    assert world_obj["world_id"] == WORLD_ID, _loc(
        "world_generate",
        "world.world_id",
        world_path,
        '"world_id"',
    )
    assert str(world_obj["seed"]).strip(), _loc(
        "world_generate",
        "world.seed",
        world_path,
        '"seed"',
    )
    assert str(world_obj["generator"]["id"]).strip(), _loc(
        "world_generate",
        "world.generator.id",
        world_path,
        '"generator"',
    )
    assert len(turn_rows) >= 6, _loc(
        "chat_turn",
        "turn_log row count",
        turn_log_path,
        "turn_id",
    )
    assert turn_rows[-1]["user_input"] == "SMOKE_FULL_CHAT", _loc(
        "chat_turn",
        "turn_log.last.user_input",
        turn_log_path,
        "SMOKE_FULL_CHAT",
    )
    assert turn_rows[-1]["assistant_text"].strip(), _loc(
        "chat_turn",
        "turn_log.last.assistant_text",
        turn_log_path,
        "assistant_text",
    )
