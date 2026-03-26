from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services import keyring as keyring_module
from backend.tools import setup_keyring as cli_module


def _write_example_config(repo_root: Path) -> None:
    config_dir = repo_root / "storage" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "llm_config.example.json").write_text(
        json.dumps(
            {
                "current_profile": "local",
                "profiles": {
                    "local": {
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4.1-mini",
                        "temperature": 0.2,
                        "api_key_ref": "primary",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_setup_keyring_cli_copies_example_and_creates_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    _write_example_config(tmp_path)

    prompts = iter(["test-api-key", "test-passphrase"])
    monkeypatch.setattr(
        keyring_module,
        "_prompt_secret",
        lambda _prompt: next(prompts),
    )
    monkeypatch.chdir(tmp_path)
    keyring_module.clear_cached_master_key()

    exit_code = cli_module.main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Created" in captured.out
    assert "Keyring entry is now initialized" in captured.out
    assert (tmp_path / "storage" / "config" / "llm_config.json").exists()
    assert (tmp_path / "storage" / "secrets" / "keyring.json").exists()

