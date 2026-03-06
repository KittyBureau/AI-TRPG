from __future__ import annotations

from typing import Dict

from backend.services.keyring import (
    clear_cached_master_key,
    describe_keyring_requirement,
    get_api_key,
    unlock_keyring,
)
from backend.services.llm_config import get_active_profile, load_llm_config

_runtime_readiness: Dict[str, object] = {
    "ready": False,
    "reason": "startup_check_pending",
}


def get_runtime_readiness() -> Dict[str, object]:
    return dict(_runtime_readiness)


def refresh_runtime_readiness() -> Dict[str, object]:
    try:
        config = load_llm_config()
    except FileNotFoundError:
        return _set_runtime_readiness(ready=False, reason="config_missing")
    except ValueError:
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")

    try:
        profile = get_active_profile(config)
    except ValueError:
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")

    requirement = describe_keyring_requirement(profile.api_key_ref)
    if requirement == "keyring_missing":
        return _set_runtime_readiness(ready=False, reason="keyring_missing")
    if requirement == "credentials_unavailable":
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")
    if requirement == "passphrase_required":
        return _set_runtime_readiness(ready=False, reason="passphrase_required")

    try:
        get_api_key(profile.api_key_ref, interactive=False)
    except FileNotFoundError:
        clear_cached_master_key()
        return _set_runtime_readiness(ready=False, reason="keyring_missing")
    except ValueError:
        clear_cached_master_key()
        return _set_runtime_readiness(ready=False, reason="keyring_locked")
    except RuntimeError:
        clear_cached_master_key()
        return _set_runtime_readiness(ready=False, reason="passphrase_required")
    return _set_runtime_readiness(ready=True, reason="ready")


def unlock_runtime_credentials(passphrase: str) -> Dict[str, object]:
    try:
        config = load_llm_config()
    except FileNotFoundError:
        return _set_runtime_readiness(ready=False, reason="config_missing")
    except ValueError:
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")

    try:
        profile = get_active_profile(config)
    except ValueError:
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")

    try:
        unlock_keyring(profile.api_key_ref, passphrase)
    except FileNotFoundError:
        return _set_runtime_readiness(ready=False, reason="keyring_missing")
    except ValueError:
        clear_cached_master_key()
        return _set_runtime_readiness(ready=False, reason="keyring_locked")
    except RuntimeError:
        clear_cached_master_key()
        return _set_runtime_readiness(ready=False, reason="credentials_unavailable")
    return refresh_runtime_readiness()


def _set_runtime_readiness(*, ready: bool, reason: str) -> Dict[str, object]:
    _runtime_readiness["ready"] = ready
    _runtime_readiness["reason"] = reason
    return get_runtime_readiness()
