from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.infra.resource_loader import (
    ResourceLoaderError,
    load_enabled_flow,
    load_enabled_prompt,
    load_enabled_schema,
    load_enabled_template,
)


@pytest.mark.parametrize(
    ("kind", "name", "loader", "path_value"),
    [
        ("prompts", "turn_profile_default", load_enabled_prompt, "resources/prompts/missing.txt"),
        ("flows", "play_turn_basic", load_enabled_flow, "resources/flows/missing.json"),
        ("schemas", "debug_resources_v1", load_enabled_schema, "resources/schemas/missing.json"),
        ("templates", "campaign_stub", load_enabled_template, "resources/templates/missing.json"),
    ],
)
def test_strict_resource_loaders_raise_when_enabled_file_is_missing(
    tmp_path: Path,
    kind: str,
    name: str,
    loader,
    path_value: str,
) -> None:
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                kind: {
                    name: {
                        "version": "v1",
                        "path": path_value,
                        "enabled": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ResourceLoaderError):
        loader(name, repo_root=tmp_path)


@pytest.mark.parametrize(
    ("kind", "name", "loader", "path_value", "file_content"),
    [
        (
            "prompts",
            "turn_profile_default",
            load_enabled_prompt,
            "resources/prompts/turn_profile_default_v1.txt",
            "Prompt text. Context: {{CONTEXT_JSON}}",
        ),
        (
            "flows",
            "play_turn_basic",
            load_enabled_flow,
            "resources/flows/play_turn_basic_v1.json",
            {"id": "play_turn_basic", "version": "v1", "steps": []},
        ),
        (
            "schemas",
            "debug_resources_v1",
            load_enabled_schema,
            "resources/schemas/debug_resources_v1.schema.json",
            {"type": "object"},
        ),
        (
            "templates",
            "campaign_stub",
            load_enabled_template,
            "resources/templates/campaign_stub_v1.json",
            {"selected": {"party_character_ids": [], "active_actor_id": ""}},
        ),
    ],
)
def test_strict_resource_loaders_ignore_manifest_hash_mismatch(
    tmp_path: Path,
    kind: str,
    name: str,
    loader,
    path_value: str,
    file_content: object,
) -> None:
    resources_dir = tmp_path / "resources"
    resource_path = tmp_path / path_value
    resource_path.parent.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(file_content, str):
        resource_path.write_text(file_content, encoding="utf-8")
    else:
        resource_path.write_text(json.dumps(file_content), encoding="utf-8")
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                kind: {
                    name: {
                        "version": "v1",
                        "path": path_value,
                        "hash": "0000000000000000000000000000000000000000000000000000000000000000",
                        "enabled": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = loader(name, repo_root=tmp_path)

    assert loaded.name == name
    assert loaded.version == "v1"
    assert Path(loaded.path).resolve() == resource_path.resolve()
    assert isinstance(loaded.source_hash, str)
    assert loaded.source_hash
    assert loaded.source_hash != "0000000000000000000000000000000000000000000000000000000000000000"
