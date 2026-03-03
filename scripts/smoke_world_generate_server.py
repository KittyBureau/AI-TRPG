from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.app.turn_service as turn_service_module
from backend.api.main import create_app


class SmokeLLMClient:
    def generate(
        self, system_prompt: str, user_input: str, debug_append: Any
    ) -> Dict[str, Any]:
        tool_calls: List[Dict[str, Any]] = []
        token = user_input.strip()

        if token == "SMOKE_A":
            tool_calls = [
                {
                    "id": "call_smoke_a",
                    "tool": "world_generate",
                    "args": {},
                }
            ]
        elif token == "SMOKE_B":
            tool_calls = [
                {
                    "id": "call_smoke_b",
                    "tool": "world_generate",
                    "args": {"world_id": "world_smoke_v1"},
                }
            ]
        elif token == "SMOKE_C":
            tool_calls = [
                {
                    "id": "call_smoke_c",
                    "tool": "world_generate",
                    "args": {"world_id": "world_smoke_v1"},
                }
            ]
        elif token == "SMOKE_D_BIND":
            tool_calls = [
                {
                    "id": "call_smoke_d_bind",
                    "tool": "world_generate",
                    "args": {"world_id": "world_bound_smoke", "bind_to_campaign": True},
                }
            ]
        elif token == "SMOKE_D_REUSE":
            tool_calls = [
                {
                    "id": "call_smoke_d_reuse",
                    "tool": "world_generate",
                    "args": {},
                }
            ]

        return {
            "assistant_text": "",
            "dialog_type": "scene_description",
            "tool_calls": tool_calls,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    # Patch turn service to avoid external LLM dependencies during smoke tests.
    turn_service_module.LLMClient = SmokeLLMClient  # type: ignore[assignment]

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
