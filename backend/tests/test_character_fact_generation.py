from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.character_fact_generation import (
    CharacterFactGenerationRequest,
    CharacterFactGenerationService,
)
from backend.app.character_facade_factory import create_runtime_character_facade
from backend.app.character_fact_llm_adapter import CharacterFactLLMResult
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


class _StubCharacterFactLLMAdapter:
    def __init__(self, drafts: list[dict[str, object]]) -> None:
        self.drafts = drafts
        self.last_system_prompt = ""
        self.last_user_payload: dict[str, object] | None = None

    def generate_drafts(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
    ) -> CharacterFactLLMResult:
        self.last_system_prompt = system_prompt
        self.last_user_payload = dict(user_payload)
        return CharacterFactLLMResult(
            drafts=[dict(item) for item in self.drafts],
            warnings=[],
        )


def _make_campaign(campaign_id: str = "camp_0001") -> Campaign:
    return Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
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
                meta={
                    "name": "Fallback Name",
                    "role": "fallback_role",
                    "tags": ["fallback"],
                },
            )
        },
    )


def test_persist_generated_batch_writes_batch_and_individual_files(
    tmp_path: Path,
) -> None:
    repo = FileRepo(tmp_path)
    service = CharacterFactGenerationService(repo)
    request = CharacterFactGenerationRequest(
        campaign_id="camp_0010",
        request_id="req 001",
        language="zh-CN",
        tone_vocab_only=False,
        count=2,
        max_count=20,
        id_policy="system",
        constraints={"allowed_roles": ["scout", "guardian"]},
    )
    drafts = [
        {
            "character_id": "bad_should_be_replaced",
            "name": "A" * 100,
            "role": "invalid_role",
            "tags": ["stealth", "stealth", "urban"],
            "attributes": {"agility": 3, "note": "fast"},
            "background": "B" * 500,
            "appearance": "C" * 300,
            "personality_tags": ["calm", "calm"],
            "position": "area_001",
            "hp": 10,
            "character_state": "alive",
            "meta": {
                "hooks": ["Debt", "Debt"],
                "language": "zh-CN",
                "source": "llm",
                "unknown": "forbidden",
            },
            "extra_field": "forbidden",
        }
    ]

    result = service.persist_generated_batch(request, drafts)

    assert (tmp_path / result.batch_path).exists()
    assert len(result.individual_paths) == 2
    for path in result.individual_paths:
        assert (tmp_path / path).exists()

    payload = json.loads((tmp_path / result.batch_path).read_text(encoding="utf-8"))
    assert payload["schema_id"] == "character_fact.v1"
    assert payload["schema_version"] == "1"
    assert payload["request_id"] == "req 001"
    assert "params" in payload
    assert payload["params"]["request_id"] == "req 001"
    assert len(payload["items"]) == 2

    first = payload["items"][0]
    assert first["character_id"].startswith("ch_")
    assert first["role"] == "scout"
    assert first["name"] == "A" * 80
    assert first["background"] == "B" * 400
    assert first["appearance"] == "C" * 240
    assert first["tags"] == ["stealth", "urban"]
    assert first["personality_tags"] == ["calm"]
    assert "position" not in first
    assert "hp" not in first
    assert "character_state" not in first
    assert "extra_field" not in first
    assert first["meta"] == {
        "hooks": ["Debt"],
        "language": "zh-CN",
        "source": "llm",
    }


def test_runtime_character_facade_prefers_individual_then_batch_and_fallback(
    tmp_path: Path,
) -> None:
    campaign = _make_campaign()
    repo = FileRepo(tmp_path)
    facade = create_runtime_character_facade(storage_root=tmp_path)

    repo.save_character_fact_batch(
        campaign.id,
        "req_001",
        {
            "schema_version": "character_fact.v1",
            "request_id": "req_001",
            "campaign_id": campaign.id,
            "items": [
                {
                    "character_id": "pc_001",
                    "name": "Batch Name",
                    "role": "batch_role",
                    "tags": ["batch"],
                    "attributes": {},
                    "background": "",
                    "appearance": "",
                    "personality_tags": [],
                }
            ],
        },
    )
    individual_path = repo.save_character_fact_draft(
        campaign.id,
        "pc_001",
        {
            "character_id": "pc_001",
            "name": "Individual Name",
            "role": "individual_role",
            "tags": ["individual"],
            "attributes": {},
            "background": "",
            "appearance": "",
            "personality_tags": [],
        },
    )

    view = facade.get_view(campaign, "pc_001")
    assert view.name == "Individual Name"
    assert view.role == "individual_role"

    individual_path.unlink()
    view_from_batch = facade.get_view(campaign, "pc_001")
    assert view_from_batch.name == "Batch Name"
    assert view_from_batch.role == "batch_role"

    for path in (tmp_path / "campaigns" / campaign.id / "characters" / "generated").glob(
        "batch_*.json"
    ):
        path.write_text("{invalid", encoding="utf-8")

    fallback = facade.get_view(campaign, "pc_001")
    assert fallback.name == "Fallback Name"
    assert fallback.role == "fallback_role"


def test_generate_and_persist_llm_mode_injects_trimmed_party_context(
    tmp_path: Path,
) -> None:
    campaign = _make_campaign()
    repo = FileRepo(tmp_path)
    repo.create_campaign(campaign)
    llm = _StubCharacterFactLLMAdapter(
        drafts=[
            {
                "character_id": "__AUTO_ID__",
                "name": "LLM Scout",
                "role": "scout",
                "tags": ["scout"],
                "attributes": {"origin": "generated"},
                "background": "",
                "appearance": "",
                "personality_tags": ["steady"],
                "meta": {"language": "zh-CN", "source": "llm", "hooks": []},
            }
        ]
    )
    service = CharacterFactGenerationService(repo, llm_adapter=llm)
    request = CharacterFactGenerationRequest(
        campaign_id=campaign.id,
        request_id="req_llm_payload_001",
        language="zh-CN",
        tone_vocab_only=False,
        constraints={"allowed_roles": ["scout"]},
        count=1,
        max_count=20,
        id_policy="system",
        draft_mode="llm",
        party_context=[
            {
                "character_id": "pc_001",
                "name": "Request Override",
                "role": "scout",
                "unknown_key": "drop me",
            },
            {
                "character_id": "pc_new",
                "name": "X" * 120,
                "role": "scout",
                "summary": "S" * 400,
                "tags": ["stealth", "stealth", "verylongtagname_should_trim_here"],
            },
        ],
    )

    result = service.generate_and_persist(request)

    assert result.count_generated == 1
    assert llm.last_user_payload is not None
    outbound_party_context = llm.last_user_payload.get("party_context")
    assert isinstance(outbound_party_context, list)
    by_id = {
        item.get("character_id"): item
        for item in outbound_party_context
        if isinstance(item, dict)
    }

    assert by_id["pc_001"]["name"] == "Fallback Name"
    assert "unknown_key" not in by_id["pc_001"]
    assert len(by_id["pc_new"]["name"]) == 80
    assert len(by_id["pc_new"]["summary"]) == 240
    assert by_id["pc_new"]["tags"] == ["stealth", "verylongtagname_should_t"]
    assert any("conflicts with storage-authoritative data" in msg for msg in result.warnings)


def test_persist_generated_batch_rolls_back_when_individual_write_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = FileRepo(tmp_path)
    service = CharacterFactGenerationService(repo)
    request = CharacterFactGenerationRequest(
        campaign_id="camp_rollback",
        request_id="req_rollback_001",
        language="zh-CN",
        tone_vocab_only=False,
        count=2,
        max_count=20,
        id_policy="system",
        constraints={"allowed_roles": ["scout", "guardian"]},
    )
    drafts = [
        {
            "character_id": "__AUTO_ID__",
            "name": "First",
            "role": "scout",
            "tags": [],
            "attributes": {},
            "background": "",
            "appearance": "",
            "personality_tags": [],
        }
    ]

    original_save = FileRepo.save_character_fact_draft
    call_count = {"value": 0}

    def _failing_save(self, campaign_id, character_file_id, payload):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise OSError("disk full")
        return original_save(self, campaign_id, character_file_id, payload)

    monkeypatch.setattr(FileRepo, "save_character_fact_draft", _failing_save)

    with pytest.raises(OSError):
        service.persist_generated_batch(request, drafts)

    generated_dir = tmp_path / "campaigns" / request.campaign_id / "characters" / "generated"
    assert sorted(generated_dir.glob("batch_*.json")) == []
    assert sorted(generated_dir.glob("*.fact.draft.json")) == []
