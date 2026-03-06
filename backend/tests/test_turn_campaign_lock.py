from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app
from backend.app.turn_service import TurnService
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _StubNoopLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "No-op turn.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


class _BlockingNoopLLM:
    started = threading.Event()
    release = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.started = threading.Event()
        cls.release = threading.Event()

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        type(self).started.set()
        if not type(self).release.wait(timeout=5):
            raise AssertionError("timed out waiting to release blocked turn")
        return {
            "assistant_text": "No-op turn.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


class _BarrierNoopLLM:
    barrier: threading.Barrier | None = None

    @classmethod
    def reset(cls, parties: int) -> None:
        cls.barrier = threading.Barrier(parties)

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        barrier = type(self).barrier
        assert barrier is not None
        try:
            barrier.wait(timeout=5)
        except threading.BrokenBarrierError as exc:
            raise AssertionError("different campaigns did not execute concurrently") from exc
        return {
            "assistant_text": "No-op turn.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


class _RaisingLLM:
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        debug_append: Any,
    ) -> Dict[str, Any]:
        raise RuntimeError("boom")


def _create_campaign(tmp_path: Path, campaign_id: str) -> None:
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
        goal=Goal(text="Stay alive.", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        map=MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Start",
                    description="Start room.",
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
    )
    repo.create_campaign(campaign)


def _threaded_turn_request(
    results: Dict[str, Dict[str, object]],
    key: str,
    campaign_id: str,
) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/chat/turn",
            json={"campaign_id": campaign_id, "user_input": "hello"},
        )
        results[key] = {
            "status_code": response.status_code,
            "json": response.json(),
        }


def test_chat_turn_returns_409_when_same_campaign_turn_is_busy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_campaign(tmp_path, "camp_lock_busy")
    monkeypatch.chdir(tmp_path)
    _BlockingNoopLLM.reset()
    monkeypatch.setattr(turn_service_module, "LLMClient", _BlockingNoopLLM)

    results: Dict[str, Dict[str, object]] = {}
    thread = threading.Thread(
        target=_threaded_turn_request,
        args=(results, "first", "camp_lock_busy"),
    )
    thread.start()
    assert _BlockingNoopLLM.started.wait(timeout=5)

    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/v1/chat/turn",
                json={"campaign_id": "camp_lock_busy", "user_input": "hello"},
            )
    finally:
        _BlockingNoopLLM.release.set()
        thread.join(timeout=5)

    assert response.status_code == 409
    assert "turn_in_progress" in response.json()["detail"]
    assert results["first"]["status_code"] == 200


def test_concurrent_turns_for_different_campaigns_do_not_block_each_other(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_lock_a")
    _create_campaign(tmp_path, "camp_lock_b")
    _BarrierNoopLLM.reset(parties=2)
    monkeypatch.setattr(turn_service_module, "LLMClient", _BarrierNoopLLM)

    repo = FileRepo(tmp_path / "storage")
    results: Dict[str, Dict[str, object]] = {}
    errors: Dict[str, BaseException] = {}

    def _worker(key: str, campaign_id: str) -> None:
        try:
            service = TurnService(repo)
            results[key] = service.submit_turn(campaign_id, "hello")
        except BaseException as exc:  # pragma: no cover - assertion path
            errors[key] = exc

    first = threading.Thread(target=_worker, args=("a", "camp_lock_a"))
    second = threading.Thread(target=_worker, args=("b", "camp_lock_b"))
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    assert errors == {}
    assert results["a"]["effective_actor_id"] == "pc_001"
    assert results["b"]["effective_actor_id"] == "pc_001"


def test_turn_lock_releases_after_turn_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_campaign(tmp_path, "camp_lock_release")
    repo = FileRepo(tmp_path / "storage")

    monkeypatch.setattr(turn_service_module, "LLMClient", _RaisingLLM)
    with pytest.raises(RuntimeError, match="boom"):
        TurnService(repo).submit_turn("camp_lock_release", "hello")

    monkeypatch.setattr(turn_service_module, "LLMClient", _StubNoopLLM)
    result = TurnService(repo).submit_turn("camp_lock_release", "hello again")

    assert result["effective_actor_id"] == "pc_001"
    assert result["narrative_text"] == "No-op turn."
