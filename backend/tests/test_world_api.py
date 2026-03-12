from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.app.turn_service import TurnService
from backend.app.world_presets import DEV_KEY_GATE_SCENARIO_WORLD_ID, build_world_preset
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.domain.world_models import World, stable_world_timestamp
from backend.infra.file_repo import FileRepo


class _ScenarioApiRuntimeLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> dict[str, Any]:
        token = user_input.strip()
        if token == "TALK_HINT":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_hint_talk",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "talk",
                            "target_id": "hint_source_001",
                            "params": {},
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
        if token == "SEARCH_CLUE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_search_clue",
                        "tool": "scene_action",
                        "args": {
                            "actor_id": "pc_001",
                            "action": "search",
                            "target_id": "clue_source_001",
                            "params": {},
                        },
                    }
                ],
            }
        if token == "MOVE_TO_GATE":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_move_gate",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_gate"},
                    }
                ],
            }
        if token == "ENTER_TARGET":
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [
                    {
                        "id": "call_enter_target",
                        "tool": "move",
                        "args": {"actor_id": "pc_001", "to_area_id": "area_target"},
                    }
                ],
            }
        return {
            "assistant_text": "No action.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _scenario_generate_request(
    *,
    world_id: str,
    name: str = "Scenario API World",
) -> dict[str, object]:
    preset = build_world_preset(DEV_KEY_GATE_SCENARIO_WORLD_ID)
    assert preset is not None
    return {
        "world_id": world_id,
        "name": name,
        "generator_id": preset.generator.id,
        "generator_params": dict(preset.generator.params),
    }


def _create_campaign(
    tmp_path: Path,
    *,
    campaign_id: str,
    world_id: str,
) -> str:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id=world_id,
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
    repo.create_campaign(campaign)
    return campaign_id


def test_get_campaign_world_lazy_creates_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(
        tmp_path, campaign_id="camp_0001", world_id="world_001"
    )

    response = client.get(f"/api/v1/campaigns/{campaign_id}/world")
    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "world_001"
    assert body["generator"]["id"] == "stub"

    world_path = tmp_path / "storage" / "worlds" / "world_001" / "world.json"
    assert world_path.exists()


def test_get_campaign_world_returns_409_when_world_id_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_0002", world_id="")

    response = client.get(f"/api/v1/campaigns/{campaign_id}/world")
    assert response.status_code == 409


def test_get_campaign_world_returns_404_when_campaign_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/campaigns/camp_missing/world")
    assert response.status_code == 404


def test_list_worlds_returns_minimal_summaries_sorted_by_updated_at_desc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileRepo(tmp_path / "storage")
    repo.save_world(
        World(
            world_id="world_old",
            name="Older World",
            seed=1,
            generator={"id": "stub", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-03T00:00:00+00:00",
            updated_at="2026-03-03T00:00:00+00:00",
        )
    )
    repo.save_world(
        World(
            world_id="world_new",
            name="Newer World",
            seed=2,
            generator={"id": "alt", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-04T00:00:00+00:00",
            updated_at="2026-03-05T00:00:00+00:00",
        )
    )
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    assert [item["world_id"] for item in body] == [
        "world_new",
        DEV_KEY_GATE_SCENARIO_WORLD_ID,
        "test_watchtower_world",
        "world_old",
    ]
    assert body[0] == {
        "world_id": "world_new",
        "name": "Newer World",
        "generator": {"id": "alt"},
        "scenario": None,
        "updated_at": "2026-03-05T00:00:00+00:00",
    }


def test_list_worlds_includes_watchtower_preset_without_storage_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    watchtower = next(
        item for item in body if item["world_id"] == "test_watchtower_world"
    )
    assert watchtower == {
        "world_id": "test_watchtower_world",
        "name": "Test Watchtower World",
        "generator": {"id": "static_test_world"},
        "scenario": None,
        "updated_at": stable_world_timestamp("test_watchtower_world"),
    }
    world_path = tmp_path / "storage" / "worlds" / "test_watchtower_world" / "world.json"
    assert not world_path.exists()


def test_list_worlds_includes_dev_scenario_preset_without_storage_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    scenario_preset = next(
        item for item in body if item["world_id"] == DEV_KEY_GATE_SCENARIO_WORLD_ID
    )
    assert scenario_preset == {
        "world_id": DEV_KEY_GATE_SCENARIO_WORLD_ID,
        "name": "Dev Key Gate Scenario World",
        "generator": {"id": "playable_scenario_v0"},
        "scenario": {
            "label": "Key Gate Scenario",
            "template_id": "key_gate_scenario",
            "area_count": 4,
            "difficulty": "easy",
        },
        "updated_at": stable_world_timestamp(DEV_KEY_GATE_SCENARIO_WORLD_ID),
    }
    world_path = (
        tmp_path
        / "storage"
        / "worlds"
        / DEV_KEY_GATE_SCENARIO_WORLD_ID
        / "world.json"
    )
    assert not world_path.exists()


def test_list_worlds_skips_invalid_world_json_without_stub_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileRepo(tmp_path / "storage")
    repo.save_world(
        World(
            world_id="world_valid",
            name="Valid World",
            seed=7,
            generator={"id": "stub", "version": "1", "params": {}},
            schema_version="1",
            created_at="2026-03-04T00:00:00+00:00",
            updated_at="2026-03-04T00:00:00+00:00",
        )
    )
    invalid_path = tmp_path / "storage" / "worlds" / "world_bad" / "world.json"
    invalid_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_path.write_text('{"world_id": ""}', encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/worlds/list")

    assert response.status_code == 200
    body = response.json()
    assert [item["world_id"] for item in body] == [
        "world_valid",
        DEV_KEY_GATE_SCENARIO_WORLD_ID,
        "test_watchtower_world",
    ]
    assert not (tmp_path / "storage" / "worlds" / "world_missing").exists()


def test_generate_world_without_campaign_creates_resource_and_is_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_new", "name": "API Generated World"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "world_api_new"
    assert body["name"] == "API Generated World"
    assert body["created"] is True
    assert body["generator"]["id"] == "stub"

    list_response = client.get("/api/v1/worlds/list")
    assert list_response.status_code == 200
    listed_ids = [item["world_id"] for item in list_response.json()]
    assert "world_api_new" in listed_ids


def test_generate_world_repeat_reuses_existing_world_without_campaign_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    first = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_repeat", "name": "Initial Name"},
    )
    second = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "world_api_repeat"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["created"] is True
    assert second_body["created"] is False
    assert second_body["world_id"] == "world_api_repeat"
    assert second_body["name"] == "Initial Name"
    assert second_body["seed"] == first_body["seed"]
    world_path = tmp_path / "storage" / "worlds" / "world_api_repeat" / "world.json"
    assert world_path.exists()
    campaigns_root = tmp_path / "storage" / "campaigns"
    if campaigns_root.exists():
        assert list(campaigns_root.glob("camp_*")) == []


def test_generate_world_rejects_blank_world_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/v1/worlds/generate", json={"world_id": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "world_id is required"


def test_generate_world_known_watchtower_preset_returns_static_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/worlds/generate",
        json={"world_id": "test_watchtower_world"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "test_watchtower_world"
    assert body["name"] == "Test Watchtower World"
    assert body["start_area"] == "village_gate"
    assert body["objective"] == "Find the tower key in the old hut and enter the watchtower."
    assert body["generator"]["id"] == "static_test_world"


def test_generate_world_can_create_scenario_backed_resource_with_normalized_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    request_body = _scenario_generate_request(world_id="world_api_scenario")

    response = client.post("/api/v1/worlds/generate", json=request_body)

    assert response.status_code == 200
    body = response.json()
    assert body["world_id"] == "world_api_scenario"
    assert body["name"] == "Scenario API World"
    assert body["created"] is True
    assert body["start_area"] == "area_start"
    assert body["generator"] == {
        "id": "playable_scenario_v0",
        "version": "1",
        "params": request_body["generator_params"],
    }

    repo = FileRepo(tmp_path / "storage")
    world = repo.get_world("world_api_scenario")
    assert world is not None
    assert world.generator.model_dump() == body["generator"]

    world_path = tmp_path / "storage" / "worlds" / "world_api_scenario" / "world.json"
    payload = json.loads(world_path.read_text(encoding="utf-8"))
    assert "map" not in payload
    assert "areas" not in payload
    assert "entities" not in payload
    assert payload["generator"] == body["generator"]


def test_generate_world_repeat_keeps_scenario_metadata_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    request_body = _scenario_generate_request(world_id="world_api_scenario_repeat")

    first = client.post("/api/v1/worlds/generate", json=request_body)
    second = client.post("/api/v1/worlds/generate", json=request_body)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["generator"] == second_body["generator"]
    assert first_body["seed"] == second_body["seed"]
    assert second_body["created"] is False


def test_generate_world_normalizes_legacy_scenario_layout_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    request_body = _scenario_generate_request(world_id="world_api_scenario_legacy")
    request_body["generator_params"] = {
        **request_body["generator_params"],
        "layout_type": "branched",
    }

    response = client.post("/api/v1/worlds/generate", json=request_body)

    assert response.status_code == 200
    body = response.json()
    assert body["generator"]["params"]["layout_type"] == "branch"


def test_generate_world_rejects_unsupported_scenario_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    request_body = _scenario_generate_request(world_id="world_bad_template")
    request_body["generator_params"] = {
        **request_body["generator_params"],
        "template_id": "unsupported_template",
    }

    response = client.post("/api/v1/worlds/generate", json=request_body)

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported scenario_template: unsupported_template"


def test_api_generated_scenario_world_is_discoverable_and_playable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/v1/worlds/generate",
        json=_scenario_generate_request(world_id="world_api_scenario_smoke"),
    )
    assert response.status_code == 200

    list_response = client.get("/api/v1/worlds/list")
    assert list_response.status_code == 200
    listed_worlds = list_response.json()
    assert "world_api_scenario_smoke" in [item["world_id"] for item in listed_worlds]
    scenario_summary = next(
        item for item in listed_worlds if item["world_id"] == "world_api_scenario_smoke"
    )
    assert scenario_summary["scenario"] == {
        "label": "Key Gate Scenario",
        "template_id": "key_gate_scenario",
        "area_count": 4,
        "difficulty": "easy",
    }

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    service.llm = _ScenarioApiRuntimeLLM()

    campaign_id = service.create_campaign(
        world_id="world_api_scenario_smoke",
        map_id="map_generated",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    talk = service.submit_turn(campaign_id, "TALK_HINT")
    assert talk["applied_actions"][0]["tool"] == "scene_action"

    service.submit_turn(campaign_id, "MOVE_TO_CLUE")
    search = service.submit_turn(campaign_id, "SEARCH_CLUE")
    assert search["state_summary"]["active_actor_inventory"] == {"required_item_001": 1}

    service.submit_turn(campaign_id, "MOVE_TO_GATE")
    entered = service.submit_turn(campaign_id, "ENTER_TARGET")
    assert entered["applied_actions"][0]["tool"] == "move"
    assert entered["state_summary"]["active_area_id"] == "area_target"

    campaign = repo.get_campaign(campaign_id)
    assert campaign.goal.status == "completed"
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "goal_achieved"
