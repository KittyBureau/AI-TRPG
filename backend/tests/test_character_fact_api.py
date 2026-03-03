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

    second = client.post(
        f"/api/v1/campaigns/{campaign_id}/characters/generate",
        json=payload,
    )
    assert second.status_code == 409
    after = sorted(generated_dir.glob("batch_*.json"))
    assert len(after) == len(before)


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
