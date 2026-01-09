import json
import os
from pathlib import Path
from typing import Any, Dict

from backend.secrets.encrypted_file_backend import (
    SecretsDecryptError,
    decrypt_secrets_file,
)

FEATURES = {"chat", "world_gen", "character_gen"}
USER_HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
APP_DIR = USER_HOME / ".ai-trpg"
SECRETS_PATH = APP_DIR / "secrets.enc"
CONFIG_PATH = APP_DIR / "config.json"

_providers: Dict[str, Dict[str, str]] = {}
_unlocked = False


class SecretsError(Exception):
    pass


class SecretsLockedError(SecretsError):
    pass


class ConfigError(SecretsError):
    pass


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError("Config file is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ConfigError("Config file must be a JSON object.")
    providers = payload.get("providers")
    if isinstance(providers, dict):
        for entry in providers.values():
            if isinstance(entry, dict) and "api_key" in entry:
                raise ConfigError("Config must not include api_key.")
    return payload


def _normalize_secrets(payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    if "providers" in payload and isinstance(payload["providers"], dict):
        providers = payload["providers"]
    elif all(isinstance(value, str) for value in payload.values()):
        if len(payload) == 1:
            only_value = next(iter(payload.values()))
            providers = {"default": {"api_key": only_value}}
        else:
            providers = {key: {"api_key": value} for key, value in payload.items()}
    else:
        raise SecretsError("Secrets payload is invalid.")

    normalized: Dict[str, Dict[str, str]] = {}
    for name, entry in providers.items():
        if not isinstance(name, str) or not name:
            raise SecretsError("Secrets payload is invalid.")
        if not isinstance(entry, dict):
            raise SecretsError("Secrets payload is invalid.")
        api_key = entry.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            raise SecretsError("Secrets payload is invalid.")
        normalized[name] = {"api_key": api_key}
    return normalized


def _require_provider_config(provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
    providers = config.get("providers")
    if not isinstance(providers, dict):
        raise ConfigError("Config missing 'providers'.")
    provider_config = providers.get(provider)
    if not isinstance(provider_config, dict):
        raise ConfigError(f"Provider config missing: {provider}")
    if "api_key" in provider_config:
        raise ConfigError("Config must not include api_key.")

    base_url = provider_config.get("base_url")
    model = provider_config.get("model")
    temperature = provider_config.get("temperature")
    timeout_seconds = provider_config.get("timeout_seconds")

    if not isinstance(base_url, str) or not base_url:
        raise ConfigError(f"Provider '{provider}' missing base_url.")
    if not isinstance(model, str) or not model:
        raise ConfigError(f"Provider '{provider}' missing model.")
    if not isinstance(temperature, (int, float)):
        raise ConfigError(f"Provider '{provider}' missing temperature.")
    if not isinstance(timeout_seconds, int):
        raise ConfigError(f"Provider '{provider}' missing timeout_seconds.")

    return {
        "base_url": base_url,
        "model": model,
        "temperature": float(temperature),
        "timeout_seconds": timeout_seconds,
    }


def unlock(password: str) -> None:
    global _providers
    global _unlocked
    try:
        secrets = decrypt_secrets_file(password, SECRETS_PATH)
    except SecretsDecryptError as exc:
        raise SecretsError("Failed to unlock secrets.") from exc

    if not isinstance(secrets, dict):
        raise SecretsError("Secrets payload is invalid.")

    _providers = _normalize_secrets(secrets)
    _unlocked = True


def is_unlocked() -> bool:
    return _unlocked


def get_client_params_for_feature(feature: str) -> Dict[str, Any]:
    if feature not in FEATURES:
        raise ConfigError(f"Unknown feature: {feature}")
    if not _unlocked:
        raise SecretsLockedError("Secrets store is locked.")

    config = _load_config(CONFIG_PATH)
    routing = config.get("routing")
    if not isinstance(routing, dict):
        raise ConfigError("Config missing 'routing'.")
    provider = routing.get(feature)
    if not provider:
        provider = routing.get("all")
    if not isinstance(provider, str) or not provider:
        raise ConfigError(f"Routing missing provider for feature: {feature}")

    provider_secret = _providers.get(provider)
    if not provider_secret:
        raise SecretsError(f"Secrets missing provider: {provider}")
    api_key = provider_secret.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        raise SecretsError(f"Secrets missing api_key for provider: {provider}")

    provider_config = _require_provider_config(provider, config)
    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": provider_config["base_url"],
        "model": provider_config["model"],
        "temperature": provider_config["temperature"],
        "timeout_seconds": provider_config["timeout_seconds"],
    }
