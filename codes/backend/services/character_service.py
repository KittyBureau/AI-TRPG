import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARACTER_DIR = REPO_ROOT / "data" / "characters"
INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')
API_KEY_ENV = "DEEPSEEK_API_KEY"
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = (
    "You generate RPG character profiles.\n"
    "Return JSON only. No code blocks. No explanations.\n"
    "Output schema:\n"
    "{\n"
    '  "character": {\n'
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


class LLMRequestError(CharacterError):
    pass


class LLMFormatError(CharacterError):
    pass


def _sanitize_name(name: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("", name).strip()
    return cleaned


def _ensure_dir() -> Path:
    CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
    return CHARACTER_DIR


def _relative_path(name: str) -> str:
    return f"data/characters/{name}.json"


def mock_generate_character(user_text: str) -> Dict[str, Any]:
    # TODO: Replace with a real LLM-driven character generator.
    seed = user_text.strip() or "Wanderer"
    name = seed.split()[0][:32] or "Wanderer"
    return {
        "name": name,
        "concept": f"A grounded character shaped by: {seed}",
        "motivation": "Pursue a concrete, realistic goal from the prompt.",
        "strength": ["Practical", "Observant"],
        "flaw": ["Stubborn"],
        "hook": [f"Tied to: {seed[:60]}"],
    }

async def _call_llm_once(user_text: str) -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise LLMRequestError(f"Missing environment variable {API_KEY_ENV}.")

    url = f"{BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.6,
        "max_tokens": 500,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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

    required_fields = ["name", "concept", "motivation", "strength", "flaw", "hook"]
    for key in required_fields:
        if key not in character:
            raise LLMFormatError(f"Character missing '{key}'.")

    _require_string_list(character.get("strength"), "strength")
    _require_string_list(character.get("flaw"), "flaw")
    _require_string_list(character.get("hook"), "hook")

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
    name = _sanitize_name(str(character.get("name", "")))
    if not name:
        raise CharacterError("Character name is empty after sanitization.")
    character["name"] = name
    directory = _ensure_dir()
    path = directory / f"{name}.json"
    if path.exists():
        raise NameConflictError(name)
    payload = json.dumps(character, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
    return _relative_path(name)
