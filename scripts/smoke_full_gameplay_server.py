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

WORLD_ID = "world_full_gameplay_v1"
SPAWN_CHARACTER_ID = "char_smoke_support"


class SmokeFullGameplayLLMClient:
    def generate(
        self, system_prompt: str, user_input: str, debug_append: Any
    ) -> Dict[str, Any]:
        tool_calls: List[Dict[str, Any]] = []
        assistant_text = ""
        token = user_input.strip()

        if token == "SMOKE_FULL_WORLD":
            tool_calls = [
                {
                    "id": "call_full_world",
                    "tool": "world_generate",
                    "args": {
                        "world_id": WORLD_ID,
                        "bind_to_campaign": True,
                    },
                }
            ]
        elif token == "SMOKE_FULL_MAP":
            tool_calls = [
                {
                    "id": "call_full_map",
                    "tool": "map_generate",
                    "args": {
                        "parent_area_id": "area_001",
                        "theme": "SmokeRoute",
                        "constraints": {"size": 2, "seed": "smoke-full"},
                    },
                }
            ]
        elif token == "SMOKE_FULL_SPAWN":
            tool_calls = [
                {
                    "id": "call_full_spawn",
                    "tool": "actor_spawn",
                    "args": {"character_id": SPAWN_CHARACTER_ID},
                }
            ]
        elif token == "SMOKE_FULL_OPTIONS":
            tool_calls = [
                {
                    "id": "call_full_options",
                    "tool": "move_options",
                    "args": {},
                }
            ]
        elif token == "SMOKE_FULL_MOVE":
            tool_calls = [
                {
                    "id": "call_full_move",
                    "tool": "move",
                    "args": {"actor_id": "pc_001", "to_area_id": "area_002"},
                }
            ]
        elif token == "SMOKE_FULL_CHAT":
            assistant_text = "The room settles. You hear only distant dripping water."
        else:
            assistant_text = "Unhandled smoke token."

        return {
            "assistant_text": assistant_text,
            "dialog_type": "scene_description",
            "tool_calls": tool_calls,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    # Patch TurnService LLM client to make the gameplay loop deterministic.
    turn_service_module.LLMClient = SmokeFullGameplayLLMClient  # type: ignore[assignment]

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
