import json
from getpass import getpass
from pathlib import Path
from typing import Any, Dict

from backend.secrets.encrypted_file_backend import (
    SecretsDecryptError,
    SecretsEncryptError,
    decrypt_secrets_file,
    encrypt_secrets_file,
)
from backend.secrets.manager import CONFIG_PATH, FEATURES, SECRETS_PATH


class SecretsCliError(Exception):
    pass


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "routing": {}, "providers": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecretsCliError("Config file is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise SecretsCliError("Config file must be a JSON object.")
    payload.setdefault("version", 1)
    payload.setdefault("routing", {})
    payload.setdefault("providers", {})
    if not isinstance(payload["routing"], dict) or not isinstance(payload["providers"], dict):
        raise SecretsCliError("Config file structure is invalid.")
    return payload


def _save_config(path: Path, config: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_secrets(password: str) -> Dict[str, Any]:
    if not SECRETS_PATH.exists():
        return {"version": 1, "providers": {}}
    try:
        payload = decrypt_secrets_file(password, SECRETS_PATH)
    except SecretsDecryptError as exc:
        raise SecretsCliError("Failed to unlock secrets.") from exc
    if not isinstance(payload, dict):
        raise SecretsCliError("Secrets payload is invalid.")
    if "providers" not in payload:
        payload = {"version": 1, "providers": {"default": {"api_key": next(iter(payload.values()), "")}}}
    payload.setdefault("version", 1)
    payload.setdefault("providers", {})
    if not isinstance(payload["providers"], dict):
        raise SecretsCliError("Secrets payload is invalid.")
    return payload


def _prompt_non_empty(label: str) -> str:
    value = input(label).strip()
    if not value:
        raise SecretsCliError("Input cannot be empty.")
    return value


def main() -> None:
    feature = _prompt_non_empty("Feature (chat/world_gen/character_gen/all): ")
    if feature != "all" and feature not in FEATURES:
        raise SecretsCliError("Unknown feature.")
    provider = _prompt_non_empty("Provider name: ")
    api_key = getpass("API key: ")
    if not api_key:
        raise SecretsCliError("API key cannot be empty.")

    password = getpass("Secrets password: ")
    if not password:
        raise SecretsCliError("Password cannot be empty.")

    secrets = _load_secrets(password)
    providers = secrets.get("providers", {})
    providers[provider] = {"api_key": api_key}
    secrets["providers"] = providers

    try:
        encrypt_secrets_file(secrets, password, SECRETS_PATH)
    except SecretsEncryptError as exc:
        raise SecretsCliError("Failed to write secrets.") from exc

    config = _load_config(CONFIG_PATH)
    if feature == "all":
        for item in FEATURES:
            config["routing"][item] = provider
    else:
        config["routing"][feature] = provider
    provider_config = config["providers"].get(provider, {})

    base_url = input("Base URL (e.g., https://.../v1): ").strip() or provider_config.get("base_url")
    if not base_url:
        raise SecretsCliError("Base URL is required.")
    model = input("Model: ").strip() or provider_config.get("model")
    if not model:
        raise SecretsCliError("Model is required.")

    temp_text = input("Temperature [0.7]: ").strip()
    if temp_text:
        try:
            temperature = float(temp_text)
        except ValueError as exc:
            raise SecretsCliError("Temperature must be a number.") from exc
    else:
        temperature = provider_config.get("temperature")
        if temperature is None:
            temperature = 0.7
        else:
            temperature = float(temperature)

    timeout_text = input("Timeout seconds [60]: ").strip()
    if timeout_text:
        try:
            timeout_seconds = int(timeout_text)
        except ValueError as exc:
            raise SecretsCliError("Timeout must be an integer.") from exc
    else:
        timeout_seconds = provider_config.get("timeout_seconds")
        if timeout_seconds is None:
            timeout_seconds = 60
        else:
            timeout_seconds = int(timeout_seconds)

    config["providers"][provider] = {
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "timeout_seconds": timeout_seconds,
    }
    _save_config(CONFIG_PATH, config)


if __name__ == "__main__":
    main()
