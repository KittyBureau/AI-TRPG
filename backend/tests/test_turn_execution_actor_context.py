from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
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


class _StubExecutionContextLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        token = user_input.strip()
        tool_calls: List[Dict[str, Any]] = []
        if token == "CTX_FALLBACK":
            tool_calls = [
                {
                    "id": "call_ctx_fallback_inventory",
                    "tool": "inventory_add",
                    "args": {
                        "item_id": "compass",
                        "quantity": 1,
                        "source_entity_id": "compass_cache",
                    },
                }
            ]
        elif token == "CTX_TARGET":
            tool_calls = [
                {
                    "id": "call_ctx_target_move",
                    "tool": "move",
                    "args": {"actor_id": "pc_002", "to_area_id": "area_002"},
                },
                {
                    "id": "call_ctx_target_inventory",
                    "tool": "inventory_add",
                    "args": {
                        "actor_id": "pc_002",
                        "item_id": "torch",
                        "quantity": 1,
                        "source_entity_id": "torch_cache",
                    },
                },
            ]
        elif token == "CTX_MISMATCH":
            tool_calls = [
                {
                    "id": "call_ctx_mismatch_move",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_002"},
                },
                {
                    "id": "call_ctx_mismatch_inventory",
                    "tool": "inventory_add",
                    "args": {
                        "actor_id": "pc_001",
                        "item_id": "torch",
                        "quantity": 1,
                        "source_entity_id": "torch_cache",
                    },
                },
            ]
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": tool_calls,
        }


def _create_campaign(tmp_path: Path, campaign_id: str) -> None:
    repo = FileRepo(tmp_path / "storage")
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001", "pc_002"],
            active_actor_id="pc_001",
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Explore and gather useful items.", status="active"),
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
                    name="Side Room",
                    description="Side room.",
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
            ),
            "pc_002": ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                inventory={},
                meta={},
            ),
        },
        entities={
            "compass_cache": Entity(
                id="compass_cache",
                kind="object",
                label="Compass Cache",
                tags=["loot_source"],
                loc=EntityLocation(type="area", id="area_001"),
                verbs=["inspect", "search"],
                state={
                    "inventory_item_id": "compass",
                    "inventory_quantity": 1,
                    "inventory_granted": False,
                },
                props={},
            ),
            "torch_cache": Entity(
                id="torch_cache",
                kind="object",
                label="Torch Cache",
                tags=["loot_source"],
                loc=EntityLocation(type="area", id="area_002"),
                verbs=["inspect", "search"],
                state={
                    "inventory_item_id": "torch",
                    "inventory_quantity": 1,
                    "inventory_granted": False,
                },
                props={},
            ),
        },
    )
    repo.create_campaign(campaign)


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", _StubExecutionContextLLM)
    return TestClient(create_app())


def test_turn_actor_context_falls_back_to_active_actor_when_execution_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_ctx_fallback")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={"campaign_id": "camp_ctx_fallback", "user_input": "CTX_FALLBACK"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_actor_id"] == "pc_001"
    assert payload["state_summary"]["active_actor_id"] == "pc_001"
    assert payload["state_summary"]["inventories"]["pc_001"]["compass"] == 1
    assert payload["state_summary"]["inventories"]["pc_002"] == {}


def test_turn_actor_context_executes_tools_for_specified_actor_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_ctx_target")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_ctx_target",
            "user_input": "CTX_TARGET",
            "execution": {"actor_id": "pc_002"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    summary = payload["state_summary"]
    assert payload["effective_actor_id"] == "pc_002"
    assert summary["active_actor_id"] == "pc_002"
    assert summary["positions"]["pc_002"] == "area_002"
    assert summary["positions"]["pc_001"] == "area_001"
    assert summary["inventories"]["pc_002"]["torch"] == 1
    assert summary["inventories"]["pc_001"] == {}


def test_turn_actor_context_execution_actor_id_takes_priority_over_legacy_actor_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_ctx_priority")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_ctx_priority",
            "user_input": "CTX_TARGET",
            "actor_id": "pc_001",
            "execution": {"actor_id": "pc_002"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    summary = payload["state_summary"]
    assert payload["effective_actor_id"] == "pc_002"
    assert summary["active_actor_id"] == "pc_002"
    assert summary["positions"]["pc_002"] == "area_002"
    assert summary["positions"]["pc_001"] == "area_001"
    assert summary["inventories"]["pc_002"]["torch"] == 1
    assert summary["inventories"]["pc_001"] == {}


def test_turn_actor_context_uses_legacy_actor_id_when_execution_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_ctx_legacy")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_ctx_legacy",
            "user_input": "CTX_TARGET",
            "actor_id": "pc_002",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    summary = payload["state_summary"]
    assert payload["effective_actor_id"] == "pc_002"
    assert summary["active_actor_id"] == "pc_002"
    assert summary["positions"]["pc_002"] == "area_002"
    assert summary["positions"]["pc_001"] == "area_001"
    assert summary["inventories"]["pc_002"]["torch"] == 1
    assert summary["inventories"]["pc_001"] == {}


def test_turn_actor_context_mismatch_rejects_tool_and_keeps_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_ctx_mismatch")
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/chat/turn",
        json={
            "campaign_id": "camp_ctx_mismatch",
            "user_input": "CTX_MISMATCH",
            "execution": {"actor_id": "pc_002"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    summary = payload["state_summary"]
    failed_calls = payload["tool_feedback"]["failed_calls"]
    assert payload["effective_actor_id"] == "pc_002"
    assert payload["applied_actions"] == []
    assert summary["positions"]["pc_001"] == "area_001"
    assert summary["positions"]["pc_002"] == "area_001"
    assert summary["inventories"]["pc_001"] == {}
    assert summary["inventories"]["pc_002"] == {}
    assert len(failed_calls) == 2
    assert {item["tool"] for item in failed_calls} == {"move", "inventory_add"}
    assert all(item["status"] == "rejected" for item in failed_calls)
    assert all(
        item["reason"] == "actor_context_mismatch" for item in failed_calls
    )
