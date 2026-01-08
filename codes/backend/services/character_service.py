import json
import re
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

from backend.secrets.manager import (
    ConfigError,
    SecretsError,
    SecretsLockedError,
    get_client_params_for_feature,
    unlock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARACTER_DIR = REPO_ROOT / "data" / "characters"
INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')
NAME_LIST_FILENAME = "_name_list.json"
FEATURE_NAME = "character_gen"

SYSTEM_PROMPT = (
    "You generate RPG character profiles.\n"
    "Return JSON only. No code blocks. No explanations.\n"
    "The character id must be file-safe (ASCII letters, digits, underscore).\n"
    "Output schema:\n"
    "{\n"
    '  "character": {\n'
    '    "id": "string",\n'
    '    "name": "string",\n'
    '    "concept": "string",\n'
    '    "motivation": "string",\n'
    '    "strength": ["string"],\n'
    '    "flaw": ["string"],\n'
    '    "hook": ["string"]\n'
    "  },\n"
    '  "comment": "short evaluation"\n'
    "}\n"
)


class CharacterError(Exception):
    pass


class NameConflictError(CharacterError):
    def __init__(self, name: str):
        super().__init__(f"Character name already exists: {name}")
        self.name = name


class IdConflictError(CharacterError):
    def __init__(self, character_id: str):
        super().__init__(f"Character id already exists: {character_id}")
        self.character_id = character_id


class LLMRequestError(CharacterError):
    pass


class LLMFormatError(CharacterError):
    pass


def _sanitize_name(name: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("", name).strip()
    return cleaned


def _sanitize_id(character_id: str) -> str:
    cleaned = character_id.strip()
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned


def _ensure_dir() -> Path:
    CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
    return CHARACTER_DIR


def _relative_path(character_id: str) -> str:
    return f"data/characters/{character_id}.json"


def _name_list_path(directory: Path) -> Path:
    return directory / NAME_LIST_FILENAME


def _save_name_list(path: Path, names: List[str]) -> None:
    payload = json.dumps(names, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")


def _rebuild_name_list(directory: Path) -> List[str]:
    names: List[str] = []
    name_list_path = _name_list_path(directory)
    for path in sorted(directory.glob("*.json")):
        if path == name_list_path:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        name = payload.get("name")
        if not isinstance(name, str):
            continue
        cleaned = _sanitize_name(name)
        if cleaned:
            names.append(cleaned)

    unique_names: List[str] = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique_names.append(name)

    _save_name_list(name_list_path, unique_names)
    return unique_names


def _load_name_list(directory: Path) -> List[str]:
    name_list_path = _name_list_path(directory)
    if not name_list_path.exists():
        return _rebuild_name_list(directory)
    try:
        payload = json.loads(name_list_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _rebuild_name_list(directory)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        return _rebuild_name_list(directory)
    return payload


def mock_generate_character(user_text: str) -> Dict[str, Any]:
    # TODO: Replace with a real LLM-driven character generator.
    seed = user_text.strip() or "Wanderer"
    name = _sanitize_name(seed.split()[0][:32] or "Wanderer") or "Wanderer"
    character_id = _sanitize_id(name) or "wanderer"
    return {
        "id": character_id,
        "name": name,
        "concept": f"A grounded character shaped by: {seed}",
        "motivation": "Pursue a concrete, realistic goal from the prompt.",
        "strength": ["Practical", "Observant"],
        "flaw": ["Stubborn"],
        "hook": [f"Tied to: {seed[:60]}"],
    }


async def _call_llm_once(user_text: str) -> str:
    try:
        params = get_client_params_for_feature(FEATURE_NAME)
    except SecretsLockedError:
        password = getpass("Secrets password: ")
        unlock(password)
        params = get_client_params_for_feature(FEATURE_NAME)
    except (SecretsError, ConfigError) as exc:
        raise LLMRequestError(str(exc)) from exc

    url = f"{params['base_url'].rstrip('/')}/chat/completions"
    payload = {
        "model": params["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": params["temperature"],
        "max_tokens": 500,
    }
    headers = {"Authorization": f"Bearer {params['api_key']}"}

    try:
        async with httpx.AsyncClient(timeout=params["timeout_seconds"]) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LLMRequestError(f"LLM request error: {exc}") from exc

    if response.status_code >= 400:
        raise LLMRequestError(
            f"LLM request failed: {response.status_code} {response.text[:200]}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMRequestError("LLM response missing message content.") from exc

    if not isinstance(content, str):
        raise LLMRequestError("LLM response content is not text.")

    return content


def _require_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise LLMFormatError(f"Field '{field}' must be a list of strings.")


def _parse_llm_output(raw: str) -> Tuple[Dict[str, Any], str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMFormatError("Model response was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise LLMFormatError("Model response must be a JSON object.")

    character = data.get("character")
    comment = data.get("comment")
    if not isinstance(character, dict):
        raise LLMFormatError("Field 'character' must be an object.")
    if not isinstance(comment, str):
        raise LLMFormatError("Field 'comment' must be a string.")

    required_fields = [
        "id",
        "name",
        "concept",
        "motivation",
        "strength",
        "flaw",
        "hook",
    ]
    for key in required_fields:
        if key not in character:
            raise LLMFormatError(f"Character missing '{key}'.")

    _require_string_list(character.get("strength"), "strength")
    _require_string_list(character.get("flaw"), "flaw")
    _require_string_list(character.get("hook"), "hook")

    character_id = _sanitize_id(str(character.get("id", "")))
    if not character_id:
        raise LLMFormatError("Character id is empty after sanitization.")
    character["id"] = character_id

    name = _sanitize_name(str(character.get("name", "")))
    if not name:
        raise LLMFormatError("Character name is empty after sanitization.")
    character["name"] = name

    return character, comment


async def generate_character(user_text: str) -> Tuple[Dict[str, Any], str]:
    last_error = None
    for attempt in range(2):
        raw = await _call_llm_once(user_text)
        try:
            return _parse_llm_output(raw)
        except LLMFormatError as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise
    raise last_error if last_error else CharacterError("Unknown LLM error.")


def rename_character(character: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    if not isinstance(character, dict):
        raise CharacterError("Character payload must be a JSON object.")
    name = _sanitize_name(new_name)
    if not name:
        raise CharacterError("New name is empty after sanitization.")
    updated = dict(character)
    updated["name"] = name
    return updated


def save_character(character: Dict[str, Any]) -> str:
    character_id = _sanitize_id(str(character.get("id", "")))
    if not character_id:
        raise CharacterError("Character id is empty after sanitization.")
    character["id"] = character_id

    name = _sanitize_name(str(character.get("name", "")))
    if not name:
        raise CharacterError("Character name is empty after sanitization.")
    character["name"] = name
    directory = _ensure_dir()
    name_list = _load_name_list(directory)
    if name in name_list:
        raise NameConflictError(name)
    path = directory / f"{character_id}.json"
    if path == _name_list_path(directory):
        raise CharacterError(f"Character id is reserved: {character_id}")
    if path.exists():
        raise IdConflictError(character_id)
    payload = json.dumps(character, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
    _rebuild_name_list(directory)
    return _relative_path(character_id)
