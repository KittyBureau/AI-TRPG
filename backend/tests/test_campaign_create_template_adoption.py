from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app


class _StubLLM:
    def generate(self, system_prompt: str, user_input: str, debug_append: object) -> dict:
        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(turn_service_module, "LLMClient", lambda: _StubLLM())
    app = create_app()
    return TestClient(app)


def _enable_create_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    original = turn_service_module.SettingsSnapshot

    def _factory() -> object:
        snapshot = original()
        snapshot.dialog.turn_profile_trace_enabled = True
        return snapshot

    monkeypatch.setattr(turn_service_module, "SettingsSnapshot", _factory)


def test_create_campaign_uses_campaign_stub_template_when_trace_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_create_trace(monkeypatch)
    resources_dir = tmp_path / "resources"
    templates_dir = resources_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps(
            {
                "selected": {
                    "party_character_ids": ["pc_template"],
                    "active_actor_id": "pc_template",
                }
            }
        ),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "templates": {
                    "campaign_stub": {
                        "version": "v1",
                        "path": "resources/templates/campaign_stub_v1.json",
                        "enabled": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    client = _client(tmp_path, monkeypatch)
    create_resp = client.post("/api/v1/campaign/create", json={})
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    campaign_id = create_body["campaign_id"]
    debug = create_body.get("debug")
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
    assert usage["name"] == "campaign_stub"
    assert usage["version"] == "v1"
    assert usage["fallback"] is False
    assert usage["applied"] is True
    assert isinstance(usage["hash"], str) and usage["hash"]

    get_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert get_resp.status_code == 200
    selected = get_resp.json()["selected"]
    assert selected["party_character_ids"] == ["pc_template"]
    assert selected["active_actor_id"] == "pc_template"


def test_create_campaign_template_conflict_falls_back_without_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_create_trace(monkeypatch)
    resources_dir = tmp_path / "resources"
    templates_dir = resources_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "campaign_stub_v1.json").write_text(
        json.dumps({"selected": {"party_character_ids": ["pc_v1"], "active_actor_id": "pc_v1"}}),
        encoding="utf-8",
    )
    (templates_dir / "campaign_stub_v2.json").write_text(
        json.dumps({"selected": {"party_character_ids": ["pc_v2"], "active_actor_id": "pc_v2"}}),
        encoding="utf-8",
    )
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "templates": {
                    "campaign_stub": [
                        {
                            "version": "v1",
                            "path": "resources/templates/campaign_stub_v1.json",
                            "enabled": True,
                        },
                        {
                            "version": "v2",
                            "path": "resources/templates/campaign_stub_v2.json",
                            "enabled": True,
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    client = _client(tmp_path, monkeypatch)
    create_resp = client.post("/api/v1/campaign/create", json={})
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    campaign_id = create_body["campaign_id"]
    debug = create_body.get("debug")
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
    assert usage["name"] == "campaign_stub"
    assert usage["fallback"] is True
    assert usage["applied"] is False

    get_resp = client.get("/api/v1/campaign/get", params={"campaign_id": campaign_id})
    assert get_resp.status_code == 200
    selected = get_resp.json()["selected"]
    assert selected["party_character_ids"] == ["pc_001"]
    assert selected["active_actor_id"] == "pc_001"


def test_create_campaign_no_trace_does_not_return_debug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    create_resp = client.post("/api/v1/campaign/create", json={})
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body.get("debug") is None
