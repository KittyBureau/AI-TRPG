from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.app.character_fact_generation import CharacterFactGenerationService
from backend.domain.models import (
    ActorState,
    Campaign,
    Goal,
    MapArea,
    Milestone,
    Selected,
    SettingsSnapshot,
)
from backend.infra.file_repo import FileRepo


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def _create_campaign(tmp_path: Path, campaign_id: str = "camp_0001") -> str:
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
        goal=Goal(text="Goal", status="active"),
        milestone=Milestone(current="intro", last_advanced_turn=0),
        actors={
            "pc_001": ActorState(
                position=None,
                hp=10,
                character_state="alive",
                meta={},
            )
        },
    )
    repo.create_campaign(campaign)
    return campaign_id


def _payload(request_id: str) -> Dict[str, Any]:
    return {
        "language": "zh-CN",
        "tone_style": ["grim", "mystery"],
        "tone_vocab_only": True,
        "allowed_tones": ["grim", "mystery", "low-magic"],
        "party_context": [
            {
                "character_id": "pc_001",
                "name": "Ava",
                "role": "scout",
                "summary": "fast recon",
                "tags": ["stealth"],
            }
        ],
        "constraints": {
            "allowed_roles": ["scout", "guardian", "speaker"],
            "style_notes": "grounded names",
        },
        "count": 3,
        "request_id": request_id,
    }


def _absolute(tmp_path: Path, rel_path: str) -> Path:
    return tmp_path / Path(rel_path)


def test_generate_returns_refs_and_writes_batch_and_individual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload("req_case_001"),
    )
    assert response.status_code == 200

    body = response.json()
    assert "items" not in body
    assert body["campaign_id"] == campaign_id
    assert body["request_id"] == "req_case_001"
    assert body["count_requested"] == 3
    assert body["count_generated"] == 3
    assert len(body["individual_paths"]) == 3

    batch_file = _absolute(tmp_path, body["batch_path"])
    assert batch_file.exists()
    batch_payload = json.loads(batch_file.read_text(encoding="utf-8"))
    assert batch_payload["schema_id"] == "character_fact.v1"
    assert batch_payload["schema_version"] == "1"
    assert batch_payload["campaign_id"] == campaign_id
    assert batch_payload["request_id"] == "req_case_001"
    assert batch_payload["params"]["party_context"][0]["character_id"] == "pc_001"
    assert batch_payload["params"]["draft_mode"] == "deterministic"
    assert len(batch_payload["items"]) == 3

    for item in batch_payload["items"]:
        assert item["character_id"] != "__AUTO_ID__"
        assert "position" not in item
        assert "hp" not in item
        assert "character_state" not in item
        fact_file = _absolute(
            tmp_path,
            f"storage/campaigns/{campaign_id}/characters/generated/{item['character_id']}.fact.draft.json",
        )
        assert fact_file.exists()

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert list(campaign.actors.keys()) == ["pc_001"]
    assert campaign.selected.party_character_ids == ["pc_001"]
    assert campaign.selected.active_actor_id == "pc_001"


def test_generate_request_id_conflict_returns_409_without_new_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    payload = _payload("req_case_conflict")

    first = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=payload,
    )
    assert first.status_code == 200

    generated_dir = (
        tmp_path / "storage" / "campaigns" / campaign_id / "characters" / "generated"
    )
    before = sorted(generated_dir.glob("batch_*.json"))
    before_drafts = sorted(generated_dir.glob("*.fact.draft.json"))

    second = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=payload,
    )
    assert second.status_code == 409
    after = sorted(generated_dir.glob("batch_*.json"))
    after_drafts = sorted(generated_dir.glob("*.fact.draft.json"))
    assert len(after) == len(before)
    assert len(after_drafts) == len(before_drafts)


def test_generate_missing_allowed_tones_returns_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    payload = _payload("req_case_bad_400")
    payload["allowed_tones"] = []
    payload["tone_vocab_only"] = True

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=payload,
    )
    assert response.status_code == 400


def test_generate_missing_campaign_keeps_404_precedence_over_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = _payload("req_case_404_precedence")
    payload["allowed_tones"] = []
    payload["tone_vocab_only"] = True

    response = client.post(
        "/api/v1/campaigns/camp_missing/characters/generate",
        json=payload,
    )
    assert response.status_code == 404


def test_generate_schema_invalid_output_returns_422(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    def _broken_normalize(
        self: CharacterFactGenerationService,
        request: Any,
        drafts: Any,
        target_count: int,
    ) -> list[dict[str, Any]]:
        return [{"name": "", "role": "scout"}]

    monkeypatch.setattr(
        CharacterFactGenerationService,
        "_run_normalize_phase",
        _broken_normalize,
    )

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload("req_case_bad_422"),
    )
    assert response.status_code == 422


def test_generate_uses_settings_draft_mode_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    settings_resp = client.post(
        "/api/v1/settings/apply",
        json={
            "campaign_id": campaign_id,
            "patch": {"characters.fact_generation.draft_mode": "llm"},
        },
    )
    assert settings_resp.status_code == 200

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload("req_case_llm_mode_001"),
    )
    assert response.status_code == 200
    body = response.json()
    batch_file = _absolute(tmp_path, body["batch_path"])
    batch_payload = json.loads(batch_file.read_text(encoding="utf-8"))
    assert batch_payload["params"]["draft_mode"] == "llm"


def test_list_batches_and_get_batch_by_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_list_001"

    created = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert created.status_code == 200

    listed = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/generated/batches",
        params={"limit": 20},
    )
    assert listed.status_code == 200
    batches = listed.json()["batches"]
    assert any(item["request_id"] == request_id for item in batches)

    fetched = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}"
    )
    assert fetched.status_code == 200
    payload = fetched.json()
    assert payload["request_id"] == request_id
    assert "params" in payload
    assert "items" in payload
    assert len(payload["items"]) == 3


def test_list_batches_survives_unreadable_batch_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_list_invalid_001"

    created = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert created.status_code == 200

    generated_dir = (
        tmp_path / "storage" / "campaigns" / campaign_id / "characters" / "generated"
    )
    (generated_dir / "batch_20260309T000000Z_bad_only.json").write_text(
        "{invalid",
        encoding="utf-8",
    )

    listed = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/generated/batches",
        params={"limit": 20},
    )
    assert listed.status_code == 200
    batches = listed.json()["batches"]
    assert any(item["request_id"] == request_id for item in batches)
    assert any(item["request_id"] == "bad_only" and item["count"] == 0 for item in batches)


def test_get_batch_missing_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    response = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/generated/batches/req_missing"
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"CharacterFact batch not found: campaign={campaign_id}, request_id=req_missing"
    )


def test_get_batch_invalid_file_returns_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    generated_dir = (
        tmp_path / "storage" / "campaigns" / campaign_id / "characters" / "generated"
    )
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "batch_20260309T000000Z_req_invalid_batch.json").write_text(
        "{invalid",
        encoding="utf-8",
    )

    response = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/generated/batches/req_invalid_batch"
    )

    assert response.status_code == 500
    assert (
        response.json()["detail"]
        == f"CharacterFact batch invalid: campaign={campaign_id}, request_id=req_invalid_batch"
    )


def test_get_fact_supports_individual_and_batch_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_fact_001"

    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]

    first_read = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}"
    )
    assert first_read.status_code == 200
    assert first_read.json()["character_id"] == character_id

    first_path.unlink()
    fallback_read = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}"
    )
    assert fallback_read.status_code == 200
    assert fallback_read.json()["character_id"] == character_id


def test_get_fact_missing_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    response = client.get(f"/api/v1/campaigns/{campaign_id}/characters/facts/ch_missing")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"CharacterFact not found: campaign={campaign_id}, character_id=ch_missing"
    )


def test_get_fact_unreadable_draft_falls_back_to_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_fact_unreadable_001"

    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]

    first_path.write_text("{invalid", encoding="utf-8")
    fallback_read = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}"
    )
    assert fallback_read.status_code == 200
    assert fallback_read.json()["character_id"] == character_id


def test_get_fact_unreadable_draft_without_batch_returns_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    generated = (
        tmp_path / "storage" / "campaigns" / campaign_id / "characters" / "generated"
    )
    generated.mkdir(parents=True, exist_ok=True)
    draft_path = generated / "ch_invalid_only.fact.draft.json"
    draft_path.write_text("{invalid", encoding="utf-8")

    response = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/ch_invalid_only"
    )

    assert response.status_code == 500
    assert (
        response.json()["detail"]
        == f"CharacterFact draft invalid: campaign={campaign_id}, character_id=ch_invalid_only"
    )


def test_get_fact_schema_invalid_draft_returns_422_without_batch_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_fact_invalid_001"

    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]

    # Keep valid JSON shape but violate strict schema validation to lock baseline 422 behavior.
    first_fact["meta"] = {"unknown": "forbidden"}
    first_path.write_text(json.dumps(first_fact), encoding="utf-8")

    invalid_read = client.get(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}"
    )
    assert invalid_read.status_code == 422


def test_adopt_fact_writes_sidecar_and_profile_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)
    request_id = "req_case_adopt_001"
    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]
    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.map.areas["area_001"] = MapArea(id="area_001", name="Start")
    campaign.actors[character_id] = ActorState(
        position="area_001",
        hp=7,
        character_state="wounded",
        inventory={"torch": 1},
        meta={
            "profile": {"legacy_only": "should_be_preserved"},
            "note": "keep",
        },
    )
    repo.save_campaign(campaign)

    first_adopt = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt",
        json={"accepted_by": "tester"},
    )
    assert first_adopt.status_code == 200
    first_body = first_adopt.json()
    assert first_body["profile_changed"] is True
    sidecar_path = _absolute(tmp_path, first_body["accepted_path"])
    assert sidecar_path.exists()
    sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_payload["accepted_by"] == "tester"
    assert sidecar_payload["character_id"] == character_id
    first_accepted_at = sidecar_payload["accepted_at"]
    adopted_campaign = repo.get_campaign(campaign_id)
    adopted_actor = adopted_campaign.actors[character_id]
    adopted_profile = adopted_actor.meta.get("profile")
    for key, value in first_fact.items():
        assert adopted_profile[key] == value
    assert adopted_profile["legacy_only"] == "should_be_preserved"
    assert adopted_actor.meta["note"] == "keep"
    assert adopted_actor.position == "area_001"
    assert adopted_actor.hp == 7
    assert adopted_actor.character_state == "wounded"
    assert adopted_actor.inventory == {"torch": 1}

    second_adopt = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt",
        json={"accepted_by": "tester"},
    )
    assert second_adopt.status_code == 200
    second_body = second_adopt.json()
    assert second_body["profile_changed"] is False
    assert second_body["acceptance_changed"] is False
    second_sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert second_sidecar["accepted_at"] == first_accepted_at


def test_adopt_fact_backfills_profile_for_legacy_actor_without_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_adopt_legacy")
    request_id = "req_case_adopt_legacy_001"
    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.map.areas["area_legacy"] = MapArea(id="area_legacy", name="Legacy Area")
    campaign.actors[character_id] = {
        "position": "area_legacy",
        "hp": 3,
        "character_state": "exhausted",
        "inventory": {"rope": 1},
    }
    repo.save_campaign(campaign)

    adopted = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt",
        json={"accepted_by": "tester"},
    )

    assert adopted.status_code == 200
    reloaded = repo.get_campaign(campaign_id)
    actor = reloaded.actors[character_id]
    assert actor.position == "area_legacy"
    assert actor.hp == 3
    assert actor.character_state == "exhausted"
    assert actor.inventory == {"rope": 1}
    assert actor.meta["profile"]["character_id"] == character_id


def test_adopt_missing_fact_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_adopt_missing")

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/ch_missing/adopt",
        json={"accepted_by": "tester"},
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"CharacterFact not found: campaign={campaign_id}, character_id=ch_missing"
    )


def test_adopt_invalid_fact_returns_422(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_adopt_invalid")
    request_id = "req_case_adopt_invalid_001"
    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]
    first_fact["meta"] = {"unknown": "forbidden"}
    first_path.write_text(json.dumps(first_fact), encoding="utf-8")

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt",
        json={"accepted_by": "tester"},
    )

    assert response.status_code == 422


def test_adopt_invalid_acceptance_sidecar_returns_500_without_profile_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_adopt_bad_sidecar")
    request_id = "req_case_adopt_bad_sidecar_001"
    generated = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=_payload(request_id),
    )
    assert generated.status_code == 200
    refs = generated.json()
    first_path = _absolute(tmp_path, refs["individual_paths"][0])
    first_fact = json.loads(first_path.read_text(encoding="utf-8"))
    character_id = first_fact["character_id"]

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.map.areas["area_sidecar"] = MapArea(id="area_sidecar", name="Sidecar Area")
    campaign.actors[character_id] = ActorState(
        position="area_sidecar",
        hp=5,
        character_state="alive",
        inventory={"coin": 1},
        meta={"profile": {"legacy_only": "keep"}},
    )
    repo.save_campaign(campaign)
    acceptance_path = repo.character_fact_acceptance_path(campaign_id, character_id)
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    acceptance_path.write_text("{invalid", encoding="utf-8")

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt",
        json={"accepted_by": "tester"},
    )

    assert response.status_code == 500
    assert (
        response.json()["detail"]
        == f"CharacterFact acceptance invalid: campaign={campaign_id}, character_id={character_id}"
    )
    reloaded = repo.get_campaign(campaign_id)
    actor = reloaded.actors[character_id]
    assert actor.meta["profile"] == {"legacy_only": "keep"}
    assert actor.position == "area_sidecar"
    assert actor.hp == 5
    assert actor.character_state == "alive"
    assert actor.inventory == {"coin": 1}


def test_openapi_docs_and_old_characters_path_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path)

    assert client.get("/api/v1/openapi.json").status_code == 200
    assert client.get("/api/v1/docs").status_code == 200
    assert (
        client.post(
            f"/api/campaigns/{campaign_id}/characters/generate",
            json=_payload("req_case_old_path"),
        ).status_code
        == 404
    )
