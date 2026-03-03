from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest

import backend.app.turn_service as turn_service_module
from backend.app.turn_service import TurnService
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _StubLLM:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload
        self.system_prompt = ""

    def generate(self, system_prompt: str, user_input: str, debug_append: Any) -> Dict[str, Any]:
        self.system_prompt = system_prompt
        return dict(self.payload)


def _make_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TurnService, FileRepo]:
    monkeypatch.setattr(
        turn_service_module,
        "LLMClient",
        lambda: _StubLLM(
            {
                "assistant_text": "Stub response.",
                "dialog_type": "scene_description",
                "tool_calls": [],
            }
        ),
    )
    repo = FileRepo(tmp_path / "storage")
    return TurnService(repo), repo


def _create_campaign(
    repo: FileRepo,
    campaign_id: str,
    *,
    party_ids: list[str] | None = None,
    active_actor_id: str = "pc_001",
) -> Campaign:
    party = party_ids or ["pc_001"]
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=party,
            active_actor_id=active_actor_id,
        ),
        settings_snapshot=SettingsSnapshot(),
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        actors={
            actor_id: ActorState(
                position="area_001",
                hp=10,
                character_state="alive",
                meta={},
            )
            for actor_id in party
        },
    )
    repo.create_campaign(campaign)
    return campaign


def _extract_prompt_context(system_prompt: str) -> Dict[str, Any]:
    marker = "Context: "
    if marker not in system_prompt:
        return {}
    return json.loads(system_prompt.rsplit(marker, 1)[1])


def test_submit_turn_blocks_when_campaign_already_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0001")
    campaign.lifecycle.ended = True
    campaign.lifecycle.reason = "goal_achieved"
    repo.save_campaign(campaign)

    with pytest.raises(ValueError, match="campaign has ended: goal_achieved"):
        service.submit_turn("camp_0001", "continue")

    assert not (tmp_path / "storage" / "campaigns" / "camp_0001" / "turn_log.jsonl").exists()


def test_unconscious_active_actor_requires_manual_switch_when_peer_alive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(
        repo,
        "camp_0002",
        party_ids=["pc_001", "pc_002"],
        active_actor_id="pc_001",
    )
    campaign.actors["pc_001"].character_state = "unconscious"
    campaign.actors["pc_002"].character_state = "alive"
    repo.save_campaign(campaign)

    with pytest.raises(ValueError, match="select_actor"):
        service.submit_turn("camp_0002", "act now")


def test_post_check_marks_party_dead_and_blocks_followup_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign(repo, "camp_0003")
    service.llm = _StubLLM(
        {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_hp_001",
                    "tool": "hp_delta",
                    "args": {
                        "target_character_id": "pc_001",
                        "delta": -20,
                        "cause": "fatal",
                    },
                }
            ],
        }
    )

    result = service.submit_turn("camp_0003", "take damage")
    assert result["dialog_type"] == "scene_description"

    campaign = repo.get_campaign("camp_0003")
    assert campaign.lifecycle.ended is True
    assert campaign.lifecycle.reason == "party_dead"
    assert campaign.lifecycle.ended_at is not None

    with pytest.raises(ValueError, match="campaign has ended: party_dead"):
        service.submit_turn("camp_0003", "another turn")


def test_milestone_advances_on_turn_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0004")
    campaign.milestone.turn_trigger_interval = 1
    repo.save_campaign(campaign)
    service.llm = _StubLLM(
        {
            "assistant_text": "Scene update.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }
    )

    service.submit_turn("camp_0004", "look around")

    updated = repo.get_campaign("camp_0004")
    assert updated.milestone.current == "milestone_1"
    assert updated.milestone.last_advanced_turn == 1
    assert updated.milestone.pressure == 0


def test_compress_enabled_uses_compressed_prompt_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0005")
    campaign.settings_snapshot.context.full_context_enabled = False
    campaign.settings_snapshot.context.compress_enabled = True
    repo.save_campaign(campaign)
    llm = _StubLLM(
        {
            "assistant_text": "Compressed response.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }
    )
    service.llm = llm

    service.submit_turn("camp_0005", "summarize")

    assert '"context_mode": "compressed"' in llm.system_prompt


def test_repeat_illegal_request_suppression_after_three_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    _create_campaign(repo, "camp_0006")
    service.llm = _StubLLM(
        {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [
                {
                    "id": "call_move_invalid",
                    "tool": "move",
                    "args": {"to_area_id": "area_001"},
                }
            ],
        }
    )
    for _ in range(3):
        result = service.submit_turn("camp_0006", "repeat invalid move")
        failed = result["tool_feedback"]["failed_calls"][0]
        assert failed["reason"] == "invalid_args"

    fourth = service.submit_turn("camp_0006", "repeat invalid move")
    failed = fourth["tool_feedback"]["failed_calls"][0]
    assert failed["reason"] == "repeat_illegal_request"


def test_turn_prompt_has_adopted_profiles_block_without_profile_duplication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0007")
    campaign.actors["pc_001"].meta = {
        "name": "Stub Name",
        "summary": "stub-summary",
        "profile": {
            "character_id": "pc_001",
            "name": "Adopted Name",
            "role": "scout",
            "tags": ["stealth"],
        },
    }
    repo.save_campaign(campaign)
    llm = _StubLLM(
        {
            "assistant_text": "ok",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }
    )
    service.llm = llm

    service.submit_turn("camp_0007", "introduce yourself")
    context = _extract_prompt_context(llm.system_prompt)
    assert context["adopted_profiles_by_actor"]["pc_001"]["name"] == "Adopted Name"
    assert context["actors"]["pc_001"]["meta"]["name"] == "Stub Name"
    assert "profile" not in context["actors"]["pc_001"]["meta"]


def test_turn_profile_trace_debug_gated_by_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0008")
    campaign.actors["pc_001"].meta["profile"] = {
        "character_id": "pc_001",
        "name": "Trace",
        "role": "guardian",
    }
    repo.save_campaign(campaign)

    without_trace = service.submit_turn("camp_0008", "hello")
    assert "debug" not in without_trace

    campaign = repo.get_campaign("camp_0008")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)
    with_trace = service.submit_turn("camp_0008", "hello again")
    assert "debug" in with_trace
    debug = with_trace["debug"]
    assert isinstance(debug, dict)
    assert "used_profile_hash" in debug
    expected_payload = {
        "pc_001": {
            "character_id": "pc_001",
            "name": "Trace",
            "role": "guardian",
        }
    }
    expected_hash = hashlib.sha256(
        json.dumps(
            expected_payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert debug["used_profile_hash"] == expected_hash
