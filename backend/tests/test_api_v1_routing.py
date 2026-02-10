from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def test_openapi_and_docs_under_api_v1(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    openapi_resp = client.get("/api/v1/openapi.json")
    docs_resp = client.get("/api/v1/docs")

    assert openapi_resp.status_code == 200
    assert docs_resp.status_code == 200


def test_old_api_paths_are_not_routed(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    assert client.get("/api/campaign/list").status_code == 404
    assert client.post("/api/chat/turn", json={}).status_code == 404
    assert client.get("/api/map/view").status_code == 404
    assert client.get("/api/settings/schema").status_code == 404
    assert (
        client.post("/api/campaigns/camp_0001/characters/generate", json={}).status_code
        == 404
    )


def test_new_api_v1_paths_work_for_all_routers(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    campaign_resp = client.post("/api/v1/campaign/select_actor", json={})
    assert campaign_resp.status_code == 422

    # Route exists; payload invalid on purpose to avoid invoking turn runtime flow.
    chat_resp = client.post("/api/v1/chat/turn", json={})
    assert chat_resp.status_code == 422

    # Route exists; query invalid/missing by design for routing assertion.
    map_resp = client.get("/api/v1/map/view")
    assert map_resp.status_code == 422

    settings_resp = client.get("/api/v1/settings/schema")
    assert settings_resp.status_code == 422

    characters_resp = client.post(
        "/api/v1/campaigns/camp_0001/characters/generate",
        json={},
    )
    assert characters_resp.status_code == 404
