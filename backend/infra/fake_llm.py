from __future__ import annotations

import json
from typing import Any, Dict, List


class FakeLLM:
    def generate(self, user_input: str, dialog_type: str) -> Dict[str, object]:
        tool_calls = _extract_tool_calls(user_input)
        return {
            "text": f"Echo: {user_input}",
            "tool_calls": tool_calls,
            "dialog_type": dialog_type,
        }


def _extract_tool_calls(user_input: str) -> List[Dict[str, Any]]:
    stripped = user_input.strip()
    if not stripped.lower().startswith("tool:"):
        return []
    payload = stripped.split(":", 1)[1].strip()
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []
