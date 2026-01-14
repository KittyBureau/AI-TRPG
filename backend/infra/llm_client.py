from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.services.keyring import get_api_key
from backend.services.llm_config import get_active_profile, load_llm_config


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float
    timeout_sec: int
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None

    @classmethod
    def from_config(cls) -> "LLMConfig":
        config = load_llm_config()
        profile = get_active_profile(config)
        api_key = get_api_key(profile.api_key_ref)
        response_format = profile.response_format or {"type": "json_object"}
        return cls(
            base_url=profile.base_url,
            api_key=api_key,
            model=profile.model,
            temperature=profile.temperature,
            timeout_sec=profile.timeout_sec,
            max_tokens=profile.max_tokens,
            response_format=response_format,
        )


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_config()

    def generate(
        self, system_prompt: str, user_input: str, debug_append: Optional[str] = None
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if debug_append:
            messages.append({"role": "system", "content": debug_append})
        messages.append({"role": "user", "content": user_input})
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
        return _parse_model_output(content)


def _endpoint(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return f"{base}/{path.lstrip('/')}"


def _post_json(
    url: str, payload: Dict[str, Any], api_key: str, timeout: int
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


def _parse_model_output(content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"assistant_text": content, "dialog_type": "", "tool_calls": []}
    if not isinstance(data, dict):
        return {"assistant_text": content, "dialog_type": "", "tool_calls": []}
    assistant_text = data.get("assistant_text") or data.get("text") or ""
    dialog_type = data.get("dialog_type") or ""
    tool_calls = data.get("tool_calls", [])
    if not isinstance(tool_calls, list):
        tool_calls = []
    tool_calls = [item for item in tool_calls if isinstance(item, dict)]
    return {
        "assistant_text": assistant_text,
        "dialog_type": dialog_type,
        "tool_calls": tool_calls,
    }
