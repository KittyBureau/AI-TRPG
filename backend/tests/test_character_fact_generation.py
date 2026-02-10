from __future__ import annotations

import json
from pathlib import Path

from backend.app.character_fact_generation import (
    CharacterFactGenerationRequest,
    CharacterFactGenerationService,
)
from backend.app.character_facade_factory import create_runtime_character_facade
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


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

    assert Path(result.batch_path).exists()
    assert len(result.individual_paths) == 2
    for path in result.individual_paths:
        assert Path(path).exists()

    payload = json.loads(Path(result.batch_path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "character_fact.v1"
    assert payload["request_id"] == "req 001"
    assert len(payload["items"]) == 2

    first = payload["items"][0]
    assert first["character_id"] == "__AUTO_ID__"
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
