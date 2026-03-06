from __future__ import annotations

import pytest

from backend.services import keyring as keyring_module


def test_get_api_key_is_non_interactive_when_keyring_locked(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = iter(["test-api-key", "test-passphrase"])
    monkeypatch.setattr(
        keyring_module,
        "_prompt_secret",
        lambda _prompt: next(prompts),
    )
    keyring_path = tmp_path / "storage" / "secrets" / "keyring.json"
    keyring_module.clear_cached_master_key()
    keyring_module.ensure_key_exists("primary", keyring_path)
    keyring_module.clear_cached_master_key()

    def _fail_prompt(_prompt: str) -> str:
        raise AssertionError("locked runtime path must not prompt")

    monkeypatch.setattr(keyring_module, "_prompt_secret", _fail_prompt)

    with pytest.raises(RuntimeError, match="Run unlock_keyring first"):
        keyring_module.get_api_key("primary", keyring_path, interactive=False)
