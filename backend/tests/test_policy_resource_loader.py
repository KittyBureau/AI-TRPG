from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.infra.resource_loader import load_enabled_policy


def _assert_builtin_fallback(loaded) -> None:
    assert loaded.name == "turn_tool_policy"
    assert loaded.fallback is True
    assert loaded.version == "builtin-v1"
    assert loaded.path == "builtin://policy/turn_tool_policy"
    assert isinstance(loaded.content, dict)
    assert loaded.content.get("id") == "turn_tool_policy"
    assert isinstance(loaded.source_hash, str) and loaded.source_hash


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
    _assert_builtin_fallback(loaded)


@pytest.mark.parametrize(
    "manifest_payload",
    [
        {},
        {"policies": {}},
        {"policies": {"other_policy": {}}},
    ],
)
def test_load_enabled_policy_fallback_when_manifest_section_or_name_missing(
    tmp_path: Path,
    manifest_payload: dict,
) -> None:
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "manifest.json").write_text(
        json.dumps(manifest_payload),
        encoding="utf-8",
    )

    loaded = load_enabled_policy("turn_tool_policy", repo_root=tmp_path)

    _assert_builtin_fallback(loaded)


@pytest.mark.parametrize(
    "policy_entry",
    [
        "bad-entry",
        {"version": "v1", "path": "resources/policies/tool_policy_v1.json"},
        [
            {
                "version": "v1",
                "path": "resources/policies/tool_policy_v1.json",
                "enabled": True,
            },
            {
                "version": "v2",
                "path": "resources/policies/tool_policy_v2.json",
                "enabled": True,
            },
        ],
    ],
)
def test_load_enabled_policy_fallback_for_invalid_entry_shape_or_multiple_enabled(
    tmp_path: Path,
    policy_entry: object,
) -> None:
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "manifest.json").write_text(
        json.dumps({"policies": {"turn_tool_policy": policy_entry}}),
        encoding="utf-8",
    )

    loaded = load_enabled_policy("turn_tool_policy", repo_root=tmp_path)

    _assert_builtin_fallback(loaded)


@pytest.mark.parametrize("mode", ["missing", "bad_json", "invalid_content"])
def test_load_enabled_policy_fallback_for_missing_or_invalid_policy_file(
    tmp_path: Path,
    mode: str,
) -> None:
    resources_dir = tmp_path / "resources"
    policies_dir = resources_dir / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "manifest.json").write_text(
        json.dumps(
            {
                "policies": {
                    "turn_tool_policy": {
                        "version": "v1",
                        "path": "resources/policies/tool_policy_v1.json",
                        "enabled": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    policy_path = policies_dir / "tool_policy_v1.json"
    if mode == "bad_json":
        policy_path.write_text("{not-json", encoding="utf-8")
    elif mode == "invalid_content":
        policy_path.write_text(
            json.dumps({"id": "turn_tool_policy", "version": "v1"}),
            encoding="utf-8",
        )

    loaded = load_enabled_policy("turn_tool_policy", repo_root=tmp_path)

    _assert_builtin_fallback(loaded)
