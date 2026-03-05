from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from backend.infra.resource_loader import (
    load_enabled_flow,
    load_enabled_policy,
    load_enabled_prompt,
    load_enabled_schema,
    load_enabled_template,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_manifest(repo_root: Path) -> Dict[str, Any]:
    manifest_path = repo_root / "resources" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _enabled_entry(
    manifest: Dict[str, Any], kind: str, resource_name: str
) -> Dict[str, Any]:
    section = manifest.get(kind)
    assert isinstance(section, dict), f"manifest missing section: {kind}"
    raw = section.get(resource_name)
    assert raw is not None, f"manifest missing resource: {kind}.{resource_name}"
    entries = raw if isinstance(raw, list) else [raw]
    enabled = [
        item
        for item in entries
        if isinstance(item, dict) and item.get("enabled") is True
    ]
    assert len(enabled) == 1, f"{kind}.{resource_name} must have exactly one enabled entry"
    entry = enabled[0]
    assert isinstance(entry.get("hash"), str) and entry["hash"], (
        f"{kind}.{resource_name} enabled entry must include non-empty hash"
    )
    assert isinstance(entry.get("path"), str) and entry["path"]
    return entry


def test_manifest_hashes_match_loader_for_key_resource_kinds() -> None:
    repo_root = _repo_root()
    manifest = _load_manifest(repo_root)

    prompt_entry = _enabled_entry(manifest, "prompts", "turn_profile_default")
    loaded_prompt = load_enabled_prompt("turn_profile_default", repo_root=repo_root)
    assert prompt_entry["hash"] == loaded_prompt.source_hash
    assert Path(repo_root / prompt_entry["path"]).resolve() == Path(loaded_prompt.path).resolve()

    flow_entry = _enabled_entry(manifest, "flows", "play_turn_basic")
    loaded_flow = load_enabled_flow("play_turn_basic", repo_root=repo_root)
    assert flow_entry["hash"] == loaded_flow.source_hash
    assert Path(repo_root / flow_entry["path"]).resolve() == Path(loaded_flow.path).resolve()

    schema_entry = _enabled_entry(manifest, "schemas", "debug_resources_v1")
    loaded_schema = load_enabled_schema("debug_resources_v1", repo_root=repo_root)
    assert schema_entry["hash"] == loaded_schema.source_hash
    assert Path(repo_root / schema_entry["path"]).resolve() == Path(loaded_schema.path).resolve()

    template_entry = _enabled_entry(manifest, "templates", "campaign_stub")
    loaded_template = load_enabled_template("campaign_stub", repo_root=repo_root)
    assert template_entry["hash"] == loaded_template.source_hash
    assert (
        Path(repo_root / template_entry["path"]).resolve()
        == Path(loaded_template.path).resolve()
    )

    policy_entry = _enabled_entry(manifest, "policies", "turn_tool_policy")
    loaded_policy = load_enabled_policy("turn_tool_policy", repo_root=repo_root)
    assert policy_entry["hash"] == loaded_policy.source_hash
    assert Path(repo_root / policy_entry["path"]).resolve() == Path(loaded_policy.path).resolve()
