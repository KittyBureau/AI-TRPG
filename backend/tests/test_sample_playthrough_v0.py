from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.infra.file_repo import FileRepo


class _StubPlayableLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        if token == "PLAY_WORLD":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_world",
                        "tool": "world_generate",
                        "args": {"world_id": "world_playable_v0", "bind_to_campaign": True},
                    }
                ],
            }
        if token == "PLAY_MAP":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_map",
                        "tool": "map_generate",
                        "args": {
                            "parent_area_id": "area_001",
                            "theme": "Playable",
                            "constraints": {"size": 2, "seed": "playable-v0"},
                        },
                    }
                ],
            }
        if token == "PLAY_MOVE_1":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_move_1",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_003"},
                    }
                ],
            }
        if token == "PLAY_LOOT_1":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_loot_1",
                        "tool": "inventory_add",
                        "args": {"item_id": "torch", "quantity": 1},
                    }
                ],
            }
        if token == "PLAY_HURT":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_hurt",
                        "tool": "hp_delta",
                        "args": {
                            "target_character_id": "pc_001",
                            "delta": -2,
                            "cause": "tripwire trap",
                        },
                    }
                ],
            }
        if token == "PLAY_LOOT_2":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_loot_2",
                        "tool": "inventory_add",
                        "args": {"item_id": "herb", "quantity": 2},
                    }
                ],
            }
        if token == "PLAY_HEAL":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_heal",
                        "tool": "hp_delta",
                        "args": {
                            "target_character_id": "pc_001",
                            "delta": 1,
                            "cause": "field treatment",
                        },
                    }
                ],
            }
        if token == "PLAY_MOVE_2":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_play_move_2",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_001"},
                    }
                ],
            }
        return {
            "assistant_text": "You pause, assess your supplies, and plan the next move.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def test_sample_playthrough_v0_persists_state_without_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubPlayableLLM)
    client = TestClient(create_app())

    create_resp = client.post("/api/v1/campaign/create", json={})
    assert create_resp.status_code == 200
    campaign_id = create_resp.json()["campaign_id"]

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.goal.text = "Retrieve supplies and stay alive."
    repo.save_campaign(campaign)

    tokens = [
        "PLAY_WORLD",
        "PLAY_MAP",
        "PLAY_MOVE_1",
        "PLAY_LOOT_1",
        "PLAY_CHAT_1",
        "PLAY_HURT",
        "PLAY_LOOT_2",
        "PLAY_HEAL",
        "PLAY_MOVE_2",
        "PLAY_CHAT_2",
    ]

    objective_values: List[str] = []
    for token in tokens:
        turn_resp = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": token},
        )
        assert turn_resp.status_code == 200
        payload = turn_resp.json()
        summary = payload["state_summary"]
        objective_values.append(summary["objective"])

    assert len(objective_values) == 10
    assert set(objective_values) == {"Retrieve supplies and stay alive."}

    final_campaign = repo.get_campaign(campaign_id)
    final_actor = final_campaign.actors["pc_001"]
    assert final_actor.position == "area_001"
    assert final_actor.hp == 9
    assert final_actor.inventory == {"torch": 1, "herb": 2}

    turn_log_path = tmp_path / "storage" / "campaigns" / campaign_id / "turn_log.jsonl"
    rows = [
        json.loads(line)
        for line in turn_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 10
    last_summary = rows[-1]["state_summary"]
    assert last_summary["objective"] == "Retrieve supplies and stay alive."
    assert last_summary["active_area_id"] == "area_001"
    assert last_summary["active_actor_inventory"] == {"torch": 1, "herb": 2}
    assert last_summary["hp"]["pc_001"] == 9
