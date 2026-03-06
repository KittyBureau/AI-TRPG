from __future__ import annotations

import pytest

from backend.tools import unlock_keyring as cli_module


def test_unlock_keyring_cli_success(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "getpass", lambda _prompt: "test-passphrase")
    monkeypatch.setattr(
        cli_module,
        "_post_unlock",
        lambda _base_url, _passphrase: (200, {"ready": True, "reason": "ready"}, ""),
    )

    exit_code = cli_module.main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Unlock succeeded" in captured.out


def test_unlock_keyring_cli_failure(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "getpass", lambda _prompt: "wrong-passphrase")
    monkeypatch.setattr(
        cli_module,
        "_post_unlock",
        lambda _base_url, _passphrase: (
            200,
            {"ready": False, "reason": "keyring_locked"},
            "",
        ),
    )

    exit_code = cli_module.main([])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Unlock failed: keyring_locked" in captured.err
