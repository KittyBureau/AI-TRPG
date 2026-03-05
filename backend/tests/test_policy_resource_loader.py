from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.infra.resource_loader import load_enabled_policy


def test_load_enabled_policy_from_manifest() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    loaded = load_enabled_policy("turn_tool_policy", repo_root=repo_root)
    assert loaded.name == "turn_tool_policy"
    assert loaded.version == "v1"
    assert loaded.fallback is False
    expected_path = (repo_root / "resources" / "policies" / "tool_policy_v1.json").resolve()
    assert Path(loaded.path).resolve() == expected_path
    assert isinstance(loaded.content, dict)
    assert loaded.content.get("id") == "turn_tool_policy"
    raw_json = json.dumps(
        loaded.content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    assert loaded.source_hash == hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


def test_load_enabled_policy_fallback_when_manifest_missing(tmp_path: Path) -> None:
    loaded = load_enabled_policy("turn_tool_policy", repo_root=tmp_path)
    assert loaded.name == "turn_tool_policy"
    assert loaded.fallback is True
    assert loaded.version == "builtin-v1"
    assert loaded.path == "builtin://policy/turn_tool_policy"
    assert isinstance(loaded.content, dict)
    assert loaded.content.get("id") == "turn_tool_policy"
    assert isinstance(loaded.source_hash, str) and loaded.source_hash
