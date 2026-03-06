from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError as exc:
    raise RuntimeError(
        "cryptography is required for keyring encryption. Install cryptography."
    ) from exc


KEYRING_VERSION = 1
KDF_ITERATIONS = 200_000
NONCE_BYTES = 12
KEY_BYTES = 32
_cached_master_key: Optional[bytes] = None


@dataclass(frozen=True)
class KeyringData:
    salt: bytes
    keys: Dict[str, Dict[str, str]]


def get_keyring_path() -> Path:
    return Path.cwd() / "storage" / "secrets" / "keyring.json"


def clear_cached_master_key() -> None:
    global _cached_master_key
    _cached_master_key = None


def describe_keyring_requirement(
    key_ref: str, keyring_path: Optional[Path] = None
) -> str:
    path = keyring_path or get_keyring_path()
    keyring = _read_keyring(path)
    if keyring is None:
        return "keyring_missing"
    if key_ref not in keyring["keys"]:
        return "credentials_unavailable"
    if _cached_master_key is None:
        return "passphrase_required"
    return "ready"


def get_api_key(
    key_ref: str,
    keyring_path: Optional[Path] = None,
    *,
    interactive: bool = False,
    passphrase: Optional[str] = None,
) -> str:
    path = keyring_path or get_keyring_path()
    keyring = _read_keyring(path)
    if keyring is None:
        raise FileNotFoundError(f"Keyring file not found: {path}")
    if key_ref not in keyring["keys"]:
        raise RuntimeError(f"Key ref not found: {key_ref}")
    master_key = _resolve_master_key(
        keyring,
        interactive=interactive,
        passphrase=passphrase,
    )
    encrypted = keyring["keys"][key_ref]
    plaintext = _decrypt_value(master_key, encrypted, key_ref)
    _cache_master_key(master_key)
    return plaintext


def unlock_keyring(
    key_ref: str,
    passphrase: str,
    keyring_path: Optional[Path] = None,
) -> str:
    clear_cached_master_key()
    return get_api_key(
        key_ref,
        keyring_path,
        interactive=False,
        passphrase=passphrase,
    )


def ensure_key_exists(key_ref: str, keyring_path: Optional[Path] = None) -> None:
    path = keyring_path or get_keyring_path()
    keyring = _read_keyring(path)
    if keyring is None:
        keyring = _new_keyring()

    if key_ref in keyring["keys"]:
        return

    api_key = _prompt_secret(f"Enter API key for {key_ref}: ")
    master_key = _resolve_master_key(
        keyring,
        allow_create=True,
        interactive=True,
    )
    _cache_master_key(master_key)
    encrypted = _encrypt_value(master_key, api_key)
    keyring["keys"][key_ref] = encrypted
    _write_keyring(path, keyring)


def _new_keyring() -> Dict[str, Any]:
    salt = os.urandom(16)
    return {
        "version": KEYRING_VERSION,
        "kdf": {"name": "PBKDF2-HMAC-SHA256", "iterations": KDF_ITERATIONS},
        "salt": _b64encode(salt),
        "keys": {},
    }


def _read_keyring(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Keyring root must be an object: {path}")
    if data.get("version") != KEYRING_VERSION:
        raise ValueError(f"Unsupported keyring version: {path}")
    if "salt" not in data or "keys" not in data:
        raise ValueError(f"Invalid keyring structure: {path}")
    return data


def _write_keyring(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _resolve_master_key(
    keyring: Dict[str, Any],
    *,
    allow_create: bool = False,
    interactive: bool = False,
    passphrase: Optional[str] = None,
) -> bytes:
    if _cached_master_key is not None:
        return _cached_master_key
    salt_b64 = keyring.get("salt")
    if not isinstance(salt_b64, str):
        raise ValueError("Keyring missing salt.")
    salt = _b64decode(salt_b64)
    resolved_passphrase = passphrase
    if resolved_passphrase is None:
        if not interactive:
            raise RuntimeError("Keyring is locked. Run unlock_keyring first.")
        if allow_create and not keyring.get("keys"):
            resolved_passphrase = _prompt_secret("Create keyring passphrase: ")
        else:
            resolved_passphrase = _prompt_secret("Enter keyring passphrase: ")
    return _derive_key(resolved_passphrase, salt, _get_iterations(keyring))


def _cache_master_key(master_key: bytes) -> None:
    global _cached_master_key
    _cached_master_key = master_key


def _get_iterations(keyring: Dict[str, Any]) -> int:
    kdf = keyring.get("kdf", {})
    iterations = kdf.get("iterations", KDF_ITERATIONS)
    if not isinstance(iterations, int):
        raise ValueError("Keyring KDF iterations must be int.")
    return iterations


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _encrypt_value(master_key: bytes, value: str) -> Dict[str, str]:
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return {
        "nonce": _b64encode(nonce),
        "ciphertext": _b64encode(ciphertext),
    }


def _decrypt_value(master_key: bytes, entry: Dict[str, Any], key_ref: str) -> str:
    nonce_b64 = entry.get("nonce")
    cipher_b64 = entry.get("ciphertext")
    if not isinstance(nonce_b64, str) or not isinstance(cipher_b64, str):
        raise ValueError(f"Key entry invalid for {key_ref}")
    aesgcm = AESGCM(master_key)
    try:
        plaintext = aesgcm.decrypt(
            _b64decode(nonce_b64), _b64decode(cipher_b64), None
        )
    except Exception as exc:
        raise ValueError("Keyring passphrase invalid or key corrupted.") from exc
    return plaintext.decode("utf-8")


def _prompt_secret(prompt: str) -> str:
    value = getpass(prompt)
    if not value:
        raise ValueError("Secret input cannot be empty.")
    return value


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))
