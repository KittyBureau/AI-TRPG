from __future__ import annotations

import json
from pathlib import Path

from backend.infra.resource_loader import load_enabled_schema


def test_debug_resources_schema_contract_keys_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    loaded = load_enabled_schema("debug_resources_v1", repo_root=repo_root)
    schema_path = Path(loaded.path)
    assert schema_path.exists()

    payload = loaded.content
    assert payload.get("type") == "object"
    resources = payload.get("properties", {}).get("resources", {})
    assert resources.get("type") == "object"
    properties = resources.get("properties", {})
    for key in ("prompts", "flows", "schemas", "templates", "template_usage"):
        assert key in properties

    file_payload = json.loads(schema_path.read_text(encoding="utf-8"))
    assert file_payload == loaded.content
    assert isinstance(loaded.source_hash, str)
    assert loaded.source_hash
