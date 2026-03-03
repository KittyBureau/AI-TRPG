from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.keyring import get_api_key
from backend.services.llm_config import get_active_profile, load_llm_config


@dataclass(frozen=True)
class CharacterFactLLMAdapterConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float
    timeout_sec: int
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None

    @classmethod
    def from_config(cls) -> "CharacterFactLLMAdapterConfig":
        config = load_llm_config()
        profile = get_active_profile(config)
        return cls(
            base_url=profile.base_url,
            api_key=get_api_key(profile.api_key_ref),
            model=profile.model,
            temperature=profile.temperature,
            timeout_sec=profile.timeout_sec,
            max_tokens=profile.max_tokens,
            response_format=profile.response_format or {"type": "json_object"},
        )


@dataclass
class CharacterFactLLMResult:
    drafts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CharacterFactLLMAdapter:
    def __init__(self, config: Optional[CharacterFactLLMAdapterConfig] = None) -> None:
        self.config = config or CharacterFactLLMAdapterConfig.from_config()

    def generate_drafts(
        self,
        *,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> CharacterFactLLMResult:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ]
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "response_format": self.config.response_format or {"type": "json_object"},
        }
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens

        response = _post_json(
            _endpoint(self.config.base_url, "chat/completions"),
            payload,
            api_key=self.config.api_key,
            timeout=self.config.timeout_sec,
        )
        content = _extract_content(response)
        return _parse_draft_content(content)


def _endpoint(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return f"{base}/{path.lstrip('/')}"


def _post_json(
    url: str,
    payload: Dict[str, Any],
    *,
    api_key: str,
    timeout: int,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def _extract_content(response: Dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Unexpected LLM response format")


def _parse_draft_content(content: str) -> CharacterFactLLMResult:
    warnings: List[str] = []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM returned invalid JSON for character draft generation.") from exc

    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("items", [])
    else:
        raise RuntimeError("LLM draft payload must be a JSON object or array.")

    if not isinstance(raw_items, list):
        raise RuntimeError("LLM draft payload 'items' must be an array.")

    drafts: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            warnings.append(f"LLM draft item[{index}] dropped: not an object.")
            continue
        drafts.append(dict(item))

    return CharacterFactLLMResult(drafts=drafts, warnings=warnings)
