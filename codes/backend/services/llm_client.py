import json
import os

import httpx

API_KEY_ENV = "DEEPSEEK_API_KEY"
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = (
    "你是跑团主持人\n"
    "风格：写实、克制\n"
    "每次回应简短\n"
    "不回顾历史\n"
    "只允许输出 JSON\n"
    "输出格式严格为：\n"
    '{"say":"..."}'
)


class LLMError(Exception):
    pass


class LLMRequestError(LLMError):
    pass


class LLMFormatError(LLMError):
    pass


def _shorten(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


async def _call_once(player_text: str) -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise LLMRequestError(f"Missing environment variable {API_KEY_ENV}.")

    url = f"{BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": player_text},
        ],
        "temperature": 0.7,
        "max_tokens": 200,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LLMRequestError(f"LLM request error: {exc}") from exc

    if response.status_code >= 400:
        raise LLMRequestError(
            f"LLM request failed: {response.status_code} {_shorten(response.text)}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMRequestError("LLM response missing message content.") from exc

    if not isinstance(content, str):
        raise LLMRequestError("LLM response content is not text.")

    return content


def _parse_say(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMFormatError("Model response was not valid JSON.") from exc

    if not isinstance(data, dict) or set(data.keys()) != {"say"}:
        raise LLMFormatError("Model JSON must contain only a 'say' field.")

    say = data.get("say")
    if not isinstance(say, str):
        raise LLMFormatError("Model JSON field 'say' must be a string.")

    return say


async def generate_say(player_text: str) -> str:
    last_error = None
    for attempt in range(2):
        raw = await _call_once(player_text)
        try:
            return _parse_say(raw)
        except LLMFormatError as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise
    raise last_error if last_error else LLMError("Unknown LLM error.")
