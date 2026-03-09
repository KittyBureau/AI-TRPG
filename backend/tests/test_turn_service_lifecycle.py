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
from backend.infra.resource_loader import load_enabled_policy, load_enabled_schema


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


def test_turn_prompt_hygiene_keeps_adopted_profile_and_selected_item_but_filters_internal_actor_meta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0007_hygiene")
    campaign.actors["pc_001"].inventory = {"rusty_key": 1}
    campaign.actors["pc_001"].meta = {
        "name": "Fallback Name",
        "summary": "fallback-summary",
        "character_id": "pc_001",
        "accepted_at": "2026-03-09T00:00:00Z",
        "source_draft_ref": "req_001:pc_001",
        "internal_note": "hide me",
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

    service.submit_turn("camp_0007_hygiene", "use the key", selected_item_id="rusty_key")
    context = _extract_prompt_context(llm.system_prompt)
    assert context["adopted_profiles_by_actor"]["pc_001"]["name"] == "Adopted Name"
    assert context["selected_item"] == {"id": "rusty_key", "quantity": 1}
    assert context["actors"]["pc_001"]["meta"] == {
        "name": "Fallback Name",
        "summary": "fallback-summary",
    }


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


def test_turn_profile_trace_uses_external_prompt_metadata_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0009")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    prompt_text = "You are test prompt. Context: {{CONTEXT_JSON}}"
    prompts_dir = tmp_path / "resources" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        prompt_text, encoding="utf-8"
    )
    (tmp_path / "resources" / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    llm = _StubLLM(
        {
            "assistant_text": "ok",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }
    )
    service.llm = llm

    result = service.submit_turn("camp_0009", "hello")
    assert "debug" in result
    debug = result["debug"]
    assert debug["used_prompt_name"] == "turn_profile_default"
    assert debug["used_prompt_version"] == "v1"
    source_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    assert debug["used_prompt_hash"] == source_hash
    assert debug["used_prompt_source_hash"] == source_hash
    assert isinstance(debug["used_prompt_rendered_hash"], str)
    assert debug["used_prompt_rendered_hash"]
    assert debug["used_prompt_rendered_hash"] != source_hash
    assert debug["used_prompt_variables"] == ["CONTEXT_JSON"]
    prompt_debug = debug.get("prompt")
    assert isinstance(prompt_debug, dict)
    assert prompt_debug["name"] == "turn_profile_default"
    assert prompt_debug["version"] == "v1"
    assert prompt_debug["source_hash"] == source_hash
    assert prompt_debug["rendered_hash"] == debug["used_prompt_rendered_hash"]
    assert prompt_debug["variables"] == ["CONTEXT_JSON"]
    assert prompt_debug["fallback"] is False
    assert "used_prompt_fallback" not in debug
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    for key in ("prompts", "flows", "schemas", "templates", "template_usage"):
        assert key in resources
        assert isinstance(resources[key], list)
    prompts_resources = resources.get("prompts")
    assert isinstance(prompts_resources, list) and prompts_resources
    prompt_resource = prompts_resources[0]
    assert prompt_resource["name"] == prompt_debug["name"]
    assert prompt_resource["version"] == prompt_debug["version"]
    assert prompt_resource["source_hash"] == prompt_debug["source_hash"]
    assert prompt_resource["rendered_hash"] == prompt_debug["rendered_hash"]
    assert prompt_resource["source_hash"] == debug["used_prompt_hash"]
    assert prompt_resource["rendered_hash"] == debug["used_prompt_rendered_hash"]
    assert prompt_resource["fallback"] == prompt_debug["fallback"]


def test_turn_profile_trace_falls_back_when_multiple_enabled_prompt_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0010")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    prompts_dir = tmp_path / "resources" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt v1. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (prompts_dir / "turn_profile_default_v2.txt").write_text(
        "Prompt v2. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (tmp_path / "resources" / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": [
                        {
                            "version": "v1",
                            "path": "resources/prompts/turn_profile_default_v1.txt",
                            "enabled": True,
                        },
                        {
                            "version": "v2",
                            "path": "resources/prompts/turn_profile_default_v2.txt",
                            "enabled": True,
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0010", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    assert debug.get("used_prompt_fallback") is True
    assert debug.get("used_prompt_version") == "builtin-v1"
    prompt_debug = debug.get("prompt")
    assert isinstance(prompt_debug, dict)
    assert prompt_debug.get("fallback") is True


def test_turn_profile_trace_includes_flow_metadata_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0011")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt for flow trace. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    flow_content = {
        "id": "play_turn_basic",
        "version": "v1",
        "steps": [
            {"id": "prompt_render", "kind": "prompt_render"},
            {"id": "chat_turn", "kind": "chat_turn"},
        ],
    }
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps(flow_content), encoding="utf-8"
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": [
                        {
                            "version": "v1",
                            "path": "resources/flows/play_turn_basic_v1.json",
                            "enabled": True,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0011", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    assert debug["used_flow_name"] == "play_turn_basic"
    assert debug["used_flow_version"] == "v1"
    expected_hash = hashlib.sha256(
        json.dumps(
            flow_content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    assert debug["used_flow_hash"] == expected_hash
    flow_debug = debug.get("flow")
    assert isinstance(flow_debug, dict)
    assert flow_debug["name"] == "play_turn_basic"
    assert flow_debug["version"] == "v1"
    assert flow_debug["hash"] == expected_hash
    assert flow_debug["fallback"] is False
    assert "used_flow_fallback" not in debug
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    flows_resources = resources.get("flows")
    assert isinstance(flows_resources, list) and flows_resources
    flow_resource = flows_resources[0]
    assert flow_resource["name"] == flow_debug["name"]
    assert flow_resource["version"] == flow_debug["version"]
    assert flow_resource["hash"] == flow_debug["hash"]
    assert flow_resource["fallback"] == flow_debug["fallback"]
    assert flow_resource["name"] == debug["used_flow_name"]
    assert flow_resource["version"] == debug["used_flow_version"]
    assert flow_resource["hash"] == debug["used_flow_hash"]


def test_turn_profile_trace_flow_fallback_on_multiple_enabled_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0012")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt v1. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (flows_dir / "play_turn_basic_v2.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v2", "steps": []}),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": [
                        {
                            "version": "v1",
                            "path": "resources/flows/play_turn_basic_v1.json",
                            "enabled": True,
                        },
                        {
                            "version": "v2",
                            "path": "resources/flows/play_turn_basic_v2.json",
                            "enabled": True,
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0012", "hello")
    assert result["narrative_text"] == "Stub response."
    debug = result.get("debug")
    assert isinstance(debug, dict)
    assert debug["used_flow_version"] == "builtin-v1"
    assert debug["used_flow_fallback"] is True
    flow_debug = debug.get("flow")
    assert isinstance(flow_debug, dict)
    assert flow_debug["fallback"] is True


def test_turn_profile_trace_includes_schema_metadata_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0013")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt trace with schemas. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    campaign_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"selected": {"type": "object"}},
    }
    character_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
    }
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps(campaign_schema), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps(character_schema), encoding="utf-8"
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0013", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    schemas_debug = debug.get("schemas")
    assert isinstance(schemas_debug, list)
    by_name = {
        item["name"]: item
        for item in schemas_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert "campaign_selected" in by_name
    assert "character_fact" in by_name
    assert by_name["campaign_selected"]["version"] == "v1"
    assert by_name["character_fact"]["version"] == "v1"
    assert by_name["campaign_selected"]["fallback"] is False
    assert by_name["character_fact"]["fallback"] is False
    assert isinstance(by_name["campaign_selected"]["hash"], str)
    assert isinstance(by_name["character_fact"]["hash"], str)
    assert by_name["campaign_selected"]["hash"]
    assert by_name["character_fact"]["hash"]
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    resources_schemas = resources.get("schemas")
    assert isinstance(resources_schemas, list)
    assert resources_schemas == schemas_debug


def test_turn_profile_trace_includes_debug_resources_schema_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0013b")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt trace with debug schema. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    debug_schema = {
        "type": "object",
        "properties": {
            "resources": {"type": "object"}
        },
    }
    (schemas_dir / "debug_resources_v1.schema.json").write_text(
        json.dumps(debug_schema), encoding="utf-8"
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                    "debug_resources_v1": {
                        "version": "v1",
                        "path": "resources/schemas/debug_resources_v1.schema.json",
                        "enabled": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0013b", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    schemas_debug = resources.get("schemas")
    assert isinstance(schemas_debug, list)
    by_name = {
        item["name"]: item
        for item in schemas_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert "debug_resources_v1" in by_name
    schema_meta = by_name["debug_resources_v1"]
    assert schema_meta["version"] == "v1"
    assert schema_meta["fallback"] is False

    loaded = load_enabled_schema("debug_resources_v1", repo_root=tmp_path)
    assert schema_meta["name"] == loaded.name
    assert schema_meta["version"] == loaded.version
    assert schema_meta["hash"] == loaded.source_hash


def test_turn_profile_trace_schema_fallback_on_multiple_enabled_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0014")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt v1. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v2.schema.json").write_text(
        json.dumps({"type": "object", "title": "v2"}), encoding="utf-8"
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": [
                        {
                            "version": "v1",
                            "path": "resources/schemas/character_fact_v1.schema.json",
                            "enabled": True,
                        },
                        {
                            "version": "v2",
                            "path": "resources/schemas/character_fact_v2.schema.json",
                            "enabled": True,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0014", "hello")
    assert result["narrative_text"] == "Stub response."
    debug = result.get("debug")
    assert isinstance(debug, dict)
    schemas_debug = debug.get("schemas")
    assert isinstance(schemas_debug, list)
    by_name = {
        item["name"]: item
        for item in schemas_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert by_name["campaign_selected"]["fallback"] is False
    assert by_name["character_fact"]["fallback"] is True
    assert by_name["character_fact"]["version"] == "builtin-v1"


def test_turn_profile_trace_includes_template_metadata_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0015")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    templates_dir = resources_dir / "templates"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt with templates trace. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps({"selected": {"party_character_ids": [], "active_actor_id": ""}}),
        encoding="utf-8",
    )
    (templates_dir / "character_fact_stub_v1.json").write_text(
        json.dumps({"name": "", "summary": "", "tags": [], "meta": {}}),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                },
                "templates": {
                    "campaign_stub": {
                        "version": "v1",
                        "path": "resources/templates/campaign_stub_v1.json",
                        "enabled": True,
                    },
                    "character_fact_stub": {
                        "version": "v1",
                        "path": "resources/templates/character_fact_stub_v1.json",
                        "enabled": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0015", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    assert isinstance(resources.get("prompts"), list)
    assert isinstance(resources.get("flows"), list)
    assert isinstance(resources.get("schemas"), list)
    assert isinstance(resources.get("templates"), list)
    assert isinstance(resources.get("template_usage"), list)
    assert resources.get("template_usage") == []
    templates_debug = debug.get("templates")
    assert isinstance(templates_debug, list)
    by_name = {
        item["name"]: item
        for item in templates_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert "campaign_stub" in by_name
    assert "character_fact_stub" in by_name
    assert by_name["campaign_stub"]["version"] == "v1"
    assert by_name["character_fact_stub"]["version"] == "v1"
    assert by_name["campaign_stub"]["fallback"] is False
    assert by_name["character_fact_stub"]["fallback"] is False
    assert isinstance(by_name["campaign_stub"]["hash"], str)
    assert isinstance(by_name["character_fact_stub"]["hash"], str)
    assert by_name["campaign_stub"]["hash"]
    assert by_name["character_fact_stub"]["hash"]
    resources_templates = resources.get("templates")
    assert isinstance(resources_templates, list)
    assert resources_templates == templates_debug


def test_turn_profile_trace_includes_policy_metadata_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0015b")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    templates_dir = resources_dir / "templates"
    policies_dir = resources_dir / "policies"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    policies_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt with policy trace. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "debug_resources_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps({"selected": {"party_character_ids": [], "active_actor_id": ""}}),
        encoding="utf-8",
    )
    (templates_dir / "character_fact_stub_v1.json").write_text(
        json.dumps({"name": "", "summary": "", "tags": [], "meta": {}}),
        encoding="utf-8",
    )
    (policies_dir / "tool_policy_v1.json").write_text(
        json.dumps(
            {
                "id": "turn_tool_policy",
                "version": "v1",
                "tool_allowlist_default": ["move"],
                "retry_policy": {"max_conflict_retries": 2},
                "conflict_policy": {"detector": "detect_conflicts"},
            }
        ),
        encoding="utf-8",
    )

    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                    "debug_resources_v1": {
                        "version": "v1",
                        "path": "resources/schemas/debug_resources_v1.schema.json",
                        "enabled": True,
                    },
                },
                "templates": {
                    "campaign_stub": {
                        "version": "v1",
                        "path": "resources/templates/campaign_stub_v1.json",
                        "enabled": True,
                    },
                    "character_fact_stub": {
                        "version": "v1",
                        "path": "resources/templates/character_fact_stub_v1.json",
                        "enabled": True,
                    },
                },
                "policies": {
                    "turn_tool_policy": {
                        "version": "v1",
                        "path": "resources/policies/tool_policy_v1.json",
                        "enabled": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0015b", "hello")
    debug = result.get("debug")
    assert isinstance(debug, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    policies_debug = resources.get("policies")
    assert isinstance(policies_debug, list)
    by_name = {
        item["name"]: item
        for item in policies_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert "turn_tool_policy" in by_name
    policy_meta = by_name["turn_tool_policy"]
    assert policy_meta["version"] == "v1"
    assert policy_meta["fallback"] is False

    loaded = load_enabled_policy("turn_tool_policy", repo_root=tmp_path)
    assert policy_meta["name"] == loaded.name
    assert policy_meta["version"] == loaded.version
    assert policy_meta["hash"] == loaded.source_hash


def test_turn_profile_trace_policy_fallback_keeps_turn_runtime_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0015c")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    templates_dir = resources_dir / "templates"
    policies_dir = resources_dir / "policies"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    policies_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt with policy fallback. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "debug_resources_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps({"selected": {"party_character_ids": [], "active_actor_id": ""}}),
        encoding="utf-8",
    )
    (templates_dir / "character_fact_stub_v1.json").write_text(
        json.dumps({"name": "", "summary": "", "tags": [], "meta": {}}),
        encoding="utf-8",
    )
    (policies_dir / "tool_policy_v1.json").write_text(
        json.dumps({"id": "turn_tool_policy", "version": "v1"}),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                    "debug_resources_v1": {
                        "version": "v1",
                        "path": "resources/schemas/debug_resources_v1.schema.json",
                        "enabled": True,
                    },
                },
                "templates": {
                    "campaign_stub": {
                        "version": "v1",
                        "path": "resources/templates/campaign_stub_v1.json",
                        "enabled": True,
                    },
                    "character_fact_stub": {
                        "version": "v1",
                        "path": "resources/templates/character_fact_stub_v1.json",
                        "enabled": True,
                    },
                },
                "policies": {
                    "turn_tool_policy": {
                        "version": "v1",
                        "path": "resources/policies/tool_policy_v1.json",
                        "enabled": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0015c", "hello")

    assert result["narrative_text"] == "Stub response."
    debug = result.get("debug")
    assert isinstance(debug, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    policies_debug = resources.get("policies")
    assert isinstance(policies_debug, list)
    assert policies_debug[0]["name"] == "turn_tool_policy"
    assert policies_debug[0]["version"] == "builtin-v1"
    assert policies_debug[0]["fallback"] is True


def test_turn_profile_trace_template_fallback_on_multiple_enabled_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, repo = _make_service(tmp_path, monkeypatch)
    campaign = _create_campaign(repo, "camp_0016")
    campaign.settings_snapshot.dialog.turn_profile_trace_enabled = True
    repo.save_campaign(campaign)

    resources_dir = tmp_path / "resources"
    prompts_dir = resources_dir / "prompts"
    flows_dir = resources_dir / "flows"
    schemas_dir = resources_dir / "schemas"
    templates_dir = resources_dir / "templates"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    flows_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / "turn_profile_default_v1.txt").write_text(
        "Prompt v1. Context: {{CONTEXT_JSON}}", encoding="utf-8"
    )
    (flows_dir / "play_turn_basic_v1.json").write_text(
        json.dumps({"id": "play_turn_basic", "version": "v1", "steps": []}),
        encoding="utf-8",
    )
    (schemas_dir / "campaign_selected_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (schemas_dir / "character_fact_v1.schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps({"selected": {"party_character_ids": [], "active_actor_id": ""}}),
        encoding="utf-8",
    )
    (templates_dir / "character_fact_stub_v1.json").write_text(
        json.dumps({"name": "", "summary": "", "tags": [], "meta": {}}),
        encoding="utf-8",
    )
    (templates_dir / "character_fact_stub_v2.json").write_text(
        json.dumps({"name": "v2", "summary": "", "tags": [], "meta": {}}),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "prompts": {
                    "turn_profile_default": {
                        "version": "v1",
                        "path": "resources/prompts/turn_profile_default_v1.txt",
                        "enabled": True,
                    }
                },
                "flows": {
                    "play_turn_basic": {
                        "version": "v1",
                        "path": "resources/flows/play_turn_basic_v1.json",
                        "enabled": True,
                    }
                },
                "schemas": {
                    "campaign_selected": {
                        "version": "v1",
                        "path": "resources/schemas/campaign_selected_v1.schema.json",
                        "enabled": True,
                    },
                    "character_fact": {
                        "version": "v1",
                        "path": "resources/schemas/character_fact_v1.schema.json",
                        "enabled": True,
                    },
                },
                "templates": {
                    "campaign_stub": {
                        "version": "v1",
                        "path": "resources/templates/campaign_stub_v1.json",
                        "enabled": True,
                    },
                    "character_fact_stub": [
                        {
                            "version": "v1",
                            "path": "resources/templates/character_fact_stub_v1.json",
                            "enabled": True,
                        },
                        {
                            "version": "v2",
                            "path": "resources/templates/character_fact_stub_v2.json",
                            "enabled": True,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.submit_turn("camp_0016", "hello")
    assert result["narrative_text"] == "Stub response."
    debug = result.get("debug")
    assert isinstance(debug, dict)
    templates_debug = debug.get("templates")
    assert isinstance(templates_debug, list)
    by_name = {
        item["name"]: item
        for item in templates_debug
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    assert by_name["campaign_stub"]["fallback"] is False
    assert by_name["character_fact_stub"]["fallback"] is True
    assert by_name["character_fact_stub"]["version"] == "builtin-v1"
