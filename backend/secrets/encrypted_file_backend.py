import base64
import json
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DEFAULT_SCRYPT_N = 2**14
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
KEY_LENGTH = 32


class SecretsDecryptError(Exception):
    pass


class SecretsEncryptError(Exception):
    pass


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except (ValueError, TypeError) as exc:
        raise SecretsDecryptError("Invalid secrets file encoding.") from exc


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=KEY_LENGTH,
        n=DEFAULT_SCRYPT_N,
        r=DEFAULT_SCRYPT_R,
        p=DEFAULT_SCRYPT_P,
    )
    return kdf.derive(password.encode("utf-8"))


def decrypt_secrets_file(password: str, path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SecretsDecryptError("Secrets file not found.") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsDecryptError("Invalid secrets file.") from exc
    if not isinstance(payload, dict):
        raise SecretsDecryptError("Invalid secrets file.")

    salt_b64 = payload.get("salt")
    nonce_b64 = payload.get("nonce")
    cipher_b64 = payload.get("ciphertext")
    if not all(isinstance(item, str) for item in [salt_b64, nonce_b64, cipher_b64]):
        raise SecretsDecryptError("Invalid secrets file.")

    salt = _b64decode(salt_b64)
    nonce = _b64decode(nonce_b64)
    ciphertext = _b64decode(cipher_b64)

    try:
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except (InvalidTag, ValueError) as exc:
        raise SecretsDecryptError("Failed to decrypt secrets file.") from exc
    except Exception as exc:
        raise SecretsDecryptError("Failed to decrypt secrets file.") from exc

    try:
        secrets = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecretsDecryptError("Invalid secrets payload.") from exc

    if not isinstance(secrets, dict):
        raise SecretsDecryptError("Invalid secrets payload.")

    return secrets


def encrypt_secrets_file(bundle: Dict[str, Any], password: str, path: Path) -> None:
    if not isinstance(bundle, dict):
        raise SecretsEncryptError("Invalid secrets payload.")

    try:
        plaintext = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SecretsEncryptError("Invalid secrets payload.") from exc

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    payload = {
        "version": 1,
        "salt": base64.b64encode(salt).decode("utf-8"),
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
