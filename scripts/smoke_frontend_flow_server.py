from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app


class SmokeFrontendFlowLLMClient:
    _TOOL_PATTERN = re.compile(r"Execute exactly one tool_call now:\s*([a-z_]+)\.")
    _ARGS_PATTERN = re.compile(
        r"Use args exactly:\s*(\{.*\})\.\s*Do not call any additional tools\.",
        re.DOTALL,
    )

    def generate(
        self, system_prompt: str, user_input: str, debug_append: Any
    ) -> Dict[str, Any]:
        instruction = user_input.strip()
        if instruction.startswith("[UI_FLOW_STEP]"):
            tool, args = self._parse_flow_instruction(instruction)
            if tool is not None:
                return {
                    "assistant_text": "",
                    "dialog_type": "scene_description",
                    "tool_calls": [
                        {
                            "id": f"call_ui_{tool}",
                            "tool": tool,
                            "args": args,
                        }
                    ],
                }
            return {
                "assistant_text": "",
                "dialog_type": "scene_description",
                "tool_calls": [],
            }

        return {
            "assistant_text": "UI flow narrative turn completed.",
            "dialog_type": "scene_description",
            "tool_calls": [],
        }

    def _parse_flow_instruction(self, instruction: str) -> Tuple[str | None, Dict[str, Any]]:
        tool_match = self._TOOL_PATTERN.search(instruction)
        args_match = self._ARGS_PATTERN.search(instruction)
        if tool_match is None or args_match is None:
            return None, {}
        tool = tool_match.group(1).strip()
        raw_args = args_match.group(1)
        try:
            parsed = json.loads(raw_args)
        except Exception:
            return None, {}
        if not isinstance(parsed, dict):
            return None, {}
        return tool, parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    # Patch turn service to make frontend flow prompts deterministic in smoke runs.
    turn_service_module.LLMClient = SmokeFrontendFlowLLMClient  # type: ignore[assignment]

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
