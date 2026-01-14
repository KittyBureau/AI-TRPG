from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float

    @classmethod
    def from_env(cls) -> "LLMConfig":
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("LLM_API_KEY", "")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        temperature_str = os.getenv("LLM_TEMPERATURE", "0.2")
        try:
            temperature = float(temperature_str)
        except ValueError:
            temperature = 0.2
        return cls(base_url=base_url, api_key=api_key, model=model, temperature=temperature)


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()

    def generate(
        self, system_prompt: str, user_input: str, debug_append: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.config.api_key:
            raise RuntimeError("LLM_API_KEY is required for LLMClient")
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
            "response_format": {"type": "json_object"},
        }
        response = _post_json(
            _endpoint(self.config.base_url, "chat/completions"),
            payload,
            api_key=self.config.api_key,
        )
        content = _extract_content(response)
        return _parse_model_output(content)


def _endpoint(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return f"{base}/{path.lstrip('/')}"


def _post_json(url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
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
    with urllib.request.urlopen(request, timeout=30) as response:
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
