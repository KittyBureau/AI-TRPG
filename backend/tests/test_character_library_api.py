from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
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


def _create_campaign(
    tmp_path: Path,
    *,
    campaign_id: str = "camp_0001",
    active_actor_id: str = "pc_001",
    trace_enabled: bool = False,
) -> str:
    repo = FileRepo(tmp_path / "storage")
    settings = SettingsSnapshot()
    settings.dialog.turn_profile_trace_enabled = trace_enabled
    campaign = Campaign(
        id=campaign_id,
        selected=Selected(
            world_id="world_001",
            map_id="map_001",
            party_character_ids=["pc_001"],
            active_actor_id=active_actor_id,
        ),
        settings_snapshot=settings,
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


def _write_character_fact_template_manifest(
    tmp_path: Path,
    *,
    entries: object,
) -> None:
    resources_dir = tmp_path / "resources"
    templates_dir = resources_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "manifest.json").write_text(
        json.dumps({"templates": {"character_fact_stub": entries}}),
        encoding="utf-8",
    )


def test_character_library_create_list_get_and_skip_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/characters/library",
        json={
            "name": "Rin",
            "summary": "A quiet scout.",
            "tags": ["scout", "calm"],
            "meta": {"origin": "manual"},
            "extra_note": "kept",
        },
    )
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    character_id = create_body["character_id"]
    assert create_body["ok"] is True
    assert create_body["fact"]["id"] == character_id
    assert create_body["fact"]["extra_note"] == "kept"

    library_dir = tmp_path / "storage" / "characters_library"
    bad_path = library_dir / "broken.json"
    bad_path.write_text("{invalid", encoding="utf-8")
    missing_name_path = library_dir / "ch_missing_name.json"
    missing_name_path.write_text(json.dumps({"id": "ch_missing_name"}), encoding="utf-8")
    invalid_filename_path = library_dir / "bad id.json"
    invalid_filename_path.write_text(json.dumps({"name": "Bad Stem"}), encoding="utf-8")

    list_resp = client.get("/api/v1/characters/library")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert any(item["id"] == character_id for item in listed)
    assert not any(item["id"] == "broken" for item in listed)
    assert not any(item["id"] == "ch_missing_name" for item in listed)
    assert not any(item["name"] == "Bad Stem" for item in listed)

    get_resp = client.get(f"/api/v1/characters/library/{character_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["id"] == character_id
    assert get_body["name"] == "Rin"
    assert get_body["summary"] == "A quiet scout."
    assert get_body["meta"]["origin"] == "manual"


def test_character_library_get_returns_stable_404_for_missing_character(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/characters/library/ch_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Character library fact not found: ch_missing"


def test_character_library_get_returns_stable_500_for_invalid_persisted_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    library_dir = tmp_path / "storage" / "characters_library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / "ch_broken.json").write_text(
        json.dumps({"id": "ch_broken", "summary": "missing name"}),
        encoding="utf-8",
    )

    response = client.get("/api/v1/characters/library/ch_broken")

    assert response.status_code == 500
    assert response.json()["detail"] == "Character library fact invalid: ch_broken"


def test_party_load_adds_actor_and_party_keeps_non_empty_active_actor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, active_actor_id="pc_001")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_hero001", "name": "Hero One", "summary": "Frontliner"},
    )
    assert create_resp.status_code == 200

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_hero001"},
    )
    assert load_resp.status_code == 200
    load_body = load_resp.json()
    assert load_body["ok"] is True
    assert "ch_hero001" in load_body["party_character_ids"]
    assert load_body["active_actor_id"] == "pc_001"

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert "ch_hero001" in campaign.actors
    assert "ch_hero001" in campaign.selected.party_character_ids
    assert campaign.selected.active_actor_id == "pc_001"
    actor_meta = campaign.actors["ch_hero001"].meta
    assert actor_meta["character_id"] == "ch_hero001"
    assert actor_meta["profile"]["name"] == "Hero One"
    assert actor_meta["profile"]["id"] == "ch_hero001"


def test_party_load_sets_active_actor_only_when_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_0002", active_actor_id="")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_hero002", "name": "Hero Two"},
    )
    assert create_resp.status_code == 200

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_hero002", "set_active_if_empty": True},
    )
    assert load_resp.status_code == 200
    assert load_resp.json()["active_actor_id"] == "ch_hero002"

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    assert campaign.selected.active_actor_id == "ch_hero002"
    profile = campaign.actors["ch_hero002"].meta.get("profile")
    assert isinstance(profile, dict)
    assert profile["id"] == "ch_hero002"


def test_party_load_returns_stable_500_when_character_library_entry_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_invalid_load")
    library_dir = tmp_path / "storage" / "characters_library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / "ch_invalid.json").write_text(
        json.dumps({"id": "ch_invalid", "summary": "missing name"}),
        encoding="utf-8",
    )

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_invalid"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Character library fact invalid: ch_invalid"


def test_party_load_returns_stable_404_for_missing_character_library_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_missing_load")

    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Character library fact not found: ch_missing"


def test_party_load_is_idempotent_and_preserves_runtime_authority_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_repeat_load")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_repeat", "name": "Repeat Hero", "summary": "stable profile"},
    )
    assert create_resp.status_code == 200

    first_load = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_repeat"},
    )
    assert first_load.status_code == 200

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.map.areas["area_keep"] = MapArea(id="area_keep", name="Keep")
    actor = campaign.actors["ch_repeat"]
    actor.position = "area_keep"
    actor.hp = 4
    actor.character_state = "wounded"
    actor.inventory = {"torch": 2}
    actor.meta["profile"]["custom_note"] = "keep"
    actor.meta["other_meta"] = "preserve"
    repo.save_campaign(campaign)

    second_load = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_repeat"},
    )
    assert second_load.status_code == 200
    load_body = second_load.json()
    assert load_body["party_character_ids"].count("ch_repeat") == 1

    reloaded = repo.get_campaign(campaign_id)
    repeated_actor = reloaded.actors["ch_repeat"]
    assert reloaded.selected.party_character_ids.count("ch_repeat") == 1
    assert repeated_actor.position == "area_keep"
    assert repeated_actor.hp == 4
    assert repeated_actor.character_state == "wounded"
    assert repeated_actor.inventory == {"torch": 2}
    assert repeated_actor.meta["character_id"] == "ch_repeat"
    assert repeated_actor.meta["other_meta"] == "preserve"
    assert repeated_actor.meta["profile"]["id"] == "ch_repeat"
    assert repeated_actor.meta["profile"]["name"] == "Repeat Hero"
    assert repeated_actor.meta["profile"]["custom_note"] == "keep"


def test_party_load_backfills_profile_metadata_for_legacy_actor_without_resetting_runtime_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    campaign_id = _create_campaign(tmp_path, campaign_id="camp_legacy_load")

    create_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_legacy", "name": "Legacy Hero", "summary": "old actor"},
    )
    assert create_resp.status_code == 200

    repo = FileRepo(tmp_path / "storage")
    campaign = repo.get_campaign(campaign_id)
    campaign.map.areas["area_old"] = MapArea(id="area_old", name="Old Keep")
    campaign.actors["ch_legacy"] = ActorState(
        position="area_old",
        hp=6,
        character_state="tired",
        inventory={"rope": 1},
        meta={
            "legacy_flag": True,
            "profile": {"custom_note": "keep me"},
        },
    )
    repo.save_campaign(campaign)

    load_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/party/load",
        json={"character_id": "ch_legacy"},
    )
    assert load_resp.status_code == 200
    assert load_resp.json()["party_character_ids"].count("ch_legacy") == 1

    reloaded = repo.get_campaign(campaign_id)
    actor = reloaded.actors["ch_legacy"]
    assert actor.position == "area_old"
    assert actor.hp == 6
    assert actor.character_state == "tired"
    assert actor.inventory == {"rope": 1}
    assert actor.meta["legacy_flag"] is True
    assert actor.meta["character_id"] == "ch_legacy"
    assert actor.meta["profile"]["id"] == "ch_legacy"
    assert actor.meta["profile"]["name"] == "Legacy Hero"
    assert actor.meta["profile"]["summary"] == "old actor"
    assert actor.meta["profile"]["custom_note"] == "keep me"


def test_character_library_upsert_applies_template_defaults_when_missing_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_character_fact_template_manifest(
        tmp_path,
        entries={
            "version": "v1",
            "path": "resources/templates/character_fact_stub_v1.json",
            "enabled": True,
        },
    )
    (tmp_path / "resources" / "templates" / "character_fact_stub_v1.json").write_text(
        json.dumps(
            {"summary": "from-template", "tags": ["seed"], "meta": {"origin": "tmpl"}}
        ),
        encoding="utf-8",
    )
    client = _client(tmp_path, monkeypatch)

    resp = client.post(
        "/api/v1/characters/library",
        json={"name": "Template User"},
    )
    assert resp.status_code == 200
    body = resp.json()
    fact = body["fact"]
    assert fact["name"] == "Template User"
    assert fact["summary"] == "from-template"
    assert fact["tags"] == ["seed"]
    assert fact["meta"] == {"origin": "tmpl"}
    assert body.get("debug") is None


def test_character_library_upsert_invalid_payload_does_not_overwrite_valid_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/characters/library",
        json={
            "id": "ch_guarded",
            "name": "Guarded Hero",
            "summary": "kept intact",
            "tags": ["valid"],
        },
    )
    assert create_resp.status_code == 200

    invalid_resp = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_guarded", "name": "   "},
    )
    assert invalid_resp.status_code == 400
    assert invalid_resp.json()["detail"] == "name is required."

    repo = FileRepo(tmp_path / "storage")
    reloaded = repo.load_character_library_fact("ch_guarded")
    assert reloaded == {
        "id": "ch_guarded",
        "name": "Guarded Hero",
        "summary": "kept intact",
        "tags": ["valid"],
        "meta": None,
    }


def test_character_library_upsert_missing_required_name_returns_422_without_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/characters/library",
        json={"id": "ch_missing_name"},
    )

    assert response.status_code == 422
    repo = FileRepo(tmp_path / "storage")
    assert repo.load_character_library_fact("ch_missing_name") is None


def test_character_library_upsert_does_not_override_user_fields_with_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = _create_campaign(
        tmp_path,
        campaign_id="camp_trace_001",
        trace_enabled=True,
    )
    _write_character_fact_template_manifest(
        tmp_path,
        entries={
            "version": "v1",
            "path": "resources/templates/character_fact_stub_v1.json",
            "enabled": True,
        },
    )
    (tmp_path / "resources" / "templates" / "character_fact_stub_v1.json").write_text(
        json.dumps(
            {
                "summary": "template-summary",
                "tags": ["template-tag"],
                "meta": {"origin": "template"},
            }
        ),
        encoding="utf-8",
    )
    client = _client(tmp_path, monkeypatch)

    resp = client.post(
        "/api/v1/characters/library",
        json={
            "campaign_id": campaign_id,
            "name": "Manual User",
            "summary": "manual-summary",
            "tags": ["manual-tag"],
            "meta": {"origin": "manual"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    fact = body["fact"]
    assert fact["summary"] == "manual-summary"
    assert fact["tags"] == ["manual-tag"]
    assert fact["meta"] == {"origin": "manual"}
    debug = body.get("debug")
    assert isinstance(debug, dict)
    usage = debug.get("template_usage")
    assert isinstance(usage, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    for key in ("prompts", "flows", "schemas", "templates", "template_usage"):
        assert key in resources
        assert isinstance(resources[key], list)
    assert resources["prompts"] == []
    assert resources["flows"] == []
    assert resources["schemas"] == []
    assert resources["templates"] == []
    usage_events = resources.get("template_usage")
    assert isinstance(usage_events, list)
    assert usage_events and usage_events[0] == usage
    assert usage["name"] == "character_fact_stub"
    assert usage["version"] == "v1"
    assert usage["fallback"] is False
    assert usage["applied"] is False


def test_character_library_upsert_template_fallback_keeps_legacy_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = _create_campaign(
        tmp_path,
        campaign_id="camp_trace_002",
        trace_enabled=True,
    )
    _write_character_fact_template_manifest(
        tmp_path,
        entries=[
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
    )
    (tmp_path / "resources" / "templates" / "character_fact_stub_v1.json").write_text(
        json.dumps({"summary": "v1", "tags": ["v1"], "meta": {"v": 1}}),
        encoding="utf-8",
    )
    (tmp_path / "resources" / "templates" / "character_fact_stub_v2.json").write_text(
        json.dumps({"summary": "v2", "tags": ["v2"], "meta": {"v": 2}}),
        encoding="utf-8",
    )
    client = _client(tmp_path, monkeypatch)

    resp = client.post(
        "/api/v1/characters/library",
        json={"campaign_id": campaign_id, "name": "Fallback User"},
    )
    assert resp.status_code == 200
    body = resp.json()
    fact = body["fact"]
    assert fact["summary"] == ""
    assert fact["tags"] == []
    assert fact.get("meta") is None
    debug = body.get("debug")
    assert isinstance(debug, dict)
    usage = debug.get("template_usage")
    assert isinstance(usage, dict)
    resources = debug.get("resources")
    assert isinstance(resources, dict)
    for key in ("prompts", "flows", "schemas", "templates", "template_usage"):
        assert key in resources
        assert isinstance(resources[key], list)
    assert resources["prompts"] == []
    assert resources["flows"] == []
    assert resources["schemas"] == []
    assert resources["templates"] == []
    usage_events = resources.get("template_usage")
    assert isinstance(usage_events, list)
    assert usage_events and usage_events[0] == usage
    assert usage["name"] == "character_fact_stub"
    assert usage["fallback"] is True
    assert usage["applied"] is False
