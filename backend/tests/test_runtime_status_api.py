from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.app import runtime_status as runtime_status_module
from backend.services import keyring as keyring_module


def _write_runtime_fixture(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    (storage_root / "config").mkdir(parents=True, exist_ok=True)
    (storage_root / "secrets").mkdir(parents=True, exist_ok=True)
    (storage_root / "config" / "llm_config.json").write_text(
        json.dumps(
            {
                "current_profile": "local",
                "profiles": {
                    "local": {
                        "base_url": "http://127.0.0.1:9999",
                        "model": "dummy-model",
                        "temperature": 0,
                        "api_key_ref": "primary",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _write_keyring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = iter(["test-api-key", "test-passphrase"])
    monkeypatch.setattr(
        keyring_module,
        "_prompt_secret",
        lambda _prompt: next(prompts),
    )
    keyring_module.clear_cached_master_key()
    keyring_module.ensure_key_exists(
        "primary",
        tmp_path / "storage" / "secrets" / "keyring.json",
    )
    keyring_module.clear_cached_master_key()


def test_startup_precheck_does_not_call_getpass_and_returns_passphrase_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_runtime_fixture(tmp_path)
    _write_keyring(tmp_path, monkeypatch)
    runtime_status_module.refresh_runtime_readiness()
    keyring_module.clear_cached_master_key()

    def _fail_prompt(_prompt: str) -> str:
        raise AssertionError("startup should not call getpass")

    monkeypatch.setattr(keyring_module, "_prompt_secret", _fail_prompt)

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/runtime/status")

    assert response.status_code == 200
    assert response.json() == {
        "ready": False,
        "reason": "passphrase_required",
    }


def test_runtime_status_returns_ready_when_keyring_already_unlocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_runtime_fixture(tmp_path)
    _write_keyring(tmp_path, monkeypatch)
    keyring_module.unlock_keyring(
        "primary",
        "test-passphrase",
        tmp_path / "storage" / "secrets" / "keyring.json",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/runtime/status")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "reason": "ready",
    }


def test_runtime_unlock_endpoint_succeeds_and_flips_status_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_runtime_fixture(tmp_path)
    _write_keyring(tmp_path, monkeypatch)

    with TestClient(create_app()) as client:
        before = client.get("/api/v1/runtime/status")
        unlocked = client.post(
            "/api/v1/runtime/unlock",
            json={"passphrase": "test-passphrase"},
        )
        after = client.get("/api/v1/runtime/status")

    assert before.json() == {
        "ready": False,
        "reason": "passphrase_required",
    }
    assert unlocked.json() == {
        "ready": True,
        "reason": "ready",
    }
    assert after.json() == {
        "ready": True,
        "reason": "ready",
    }


def test_runtime_unlock_endpoint_failure_keeps_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_runtime_fixture(tmp_path)
    _write_keyring(tmp_path, monkeypatch)

    with TestClient(create_app()) as client:
        before = client.get("/api/v1/runtime/status")
        unlocked = client.post(
            "/api/v1/runtime/unlock",
            json={"passphrase": "wrong-passphrase"},
        )
        after = client.get("/api/v1/runtime/status")

    assert before.json() == {
        "ready": False,
        "reason": "passphrase_required",
    }
    assert unlocked.json() == {
        "ready": False,
        "reason": "keyring_locked",
    }
    assert after.json() == {
        "ready": False,
        "reason": "passphrase_required",
    }
