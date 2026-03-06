from __future__ import annotations

import hashlib
import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


class ResourceLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedPrompt:
    name: str
    version: str
    text: str
    source_hash: str
    path: str

    @property
    def hash(self) -> str:
        return self.source_hash


@dataclass(frozen=True)
class LoadedFlow:
    name: str
    version: str
    content: Dict[str, Any]
    source_hash: str
    path: str

    @property
    def hash(self) -> str:
        return self.source_hash


@dataclass(frozen=True)
class LoadedSchema:
    name: str
    version: str
    content: Dict[str, Any]
    source_hash: str
    path: str

    @property
    def hash(self) -> str:
        return self.source_hash


@dataclass(frozen=True)
class LoadedTemplate:
    name: str
    version: str
    content: Dict[str, Any]
    source_hash: str
    path: str

    @property
    def hash(self) -> str:
        return self.source_hash


@dataclass(frozen=True)
class LoadedPolicy:
    name: str
    version: str
    content: Dict[str, Any]
    source_hash: str
    path: str
    fallback: bool

    @property
    def hash(self) -> str:
        return self.source_hash


def load_enabled_prompt(name: str, *, repo_root: Path | None = None) -> LoadedPrompt:
    root = repo_root or Path.cwd()
    manifest_path = root / "resources" / "manifest.json"
    manifest = _load_manifest(manifest_path)

    prompts = manifest.get("prompts")
    if not isinstance(prompts, dict):
        raise ResourceLoaderError("resources.manifest missing 'prompts' object")
    prompt_entry = prompts.get(name)
    if prompt_entry is None:
        raise ResourceLoaderError(f"prompt '{name}' not found in manifest")

    entries = _normalize_resource_entries("prompt", name, prompt_entry)
    enabled_entries = [entry for entry in entries if entry.get("enabled") is True]
    if len(enabled_entries) == 0:
        raise ResourceLoaderError(f"prompt '{name}' has no enabled entry")
    if len(enabled_entries) > 1:
        raise ResourceLoaderError(f"prompt '{name}' has multiple enabled entries")
    entry = enabled_entries[0]

    version = entry["version"]
    path_value = entry["path"]
    prompt_path = _resolve_resource_path(path_value, root=root)
    if not prompt_path.exists():
        raise ResourceLoaderError(f"prompt file not found: {prompt_path}")

    text = prompt_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ResourceLoaderError(f"prompt '{name}' is empty: {prompt_path}")

    return LoadedPrompt(
        name=name,
        version=version,
        text=text,
        source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        path=str(prompt_path),
    )


def load_enabled_flow(name: str, *, repo_root: Path | None = None) -> LoadedFlow:
    root = repo_root or Path.cwd()
    manifest_path = root / "resources" / "manifest.json"
    manifest = _load_manifest(manifest_path)

    flows = manifest.get("flows")
    if not isinstance(flows, dict):
        raise ResourceLoaderError("resources.manifest missing 'flows' object")
    flow_entry = flows.get(name)
    if flow_entry is None:
        raise ResourceLoaderError(f"flow '{name}' not found in manifest")

    entries = _normalize_resource_entries("flow", name, flow_entry)
    enabled_entries = [entry for entry in entries if entry.get("enabled") is True]
    if len(enabled_entries) == 0:
        raise ResourceLoaderError(f"flow '{name}' has no enabled entry")
    if len(enabled_entries) > 1:
        raise ResourceLoaderError(f"flow '{name}' has multiple enabled entries")
    entry = enabled_entries[0]

    version = entry["version"]
    path_value = entry["path"]
    flow_path = _resolve_resource_path(path_value, root=root)
    if not flow_path.exists():
        raise ResourceLoaderError(f"flow file not found: {flow_path}")

    try:
        content = json.loads(flow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResourceLoaderError(f"invalid flow json: {flow_path}") from exc
    if not isinstance(content, dict):
        raise ResourceLoaderError(f"flow root must be object: {flow_path}")
    if not isinstance(content.get("id"), str) or not content["id"].strip():
        raise ResourceLoaderError(f"flow '{name}' missing id: {flow_path}")
    if not isinstance(content.get("version"), str) or not content["version"].strip():
        raise ResourceLoaderError(f"flow '{name}' missing version: {flow_path}")
    if not isinstance(content.get("steps"), list):
        raise ResourceLoaderError(f"flow '{name}' missing steps list: {flow_path}")

    raw_json = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return LoadedFlow(
        name=name,
        version=version,
        content=content,
        source_hash=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        path=str(flow_path),
    )


def load_enabled_schema(name: str, *, repo_root: Path | None = None) -> LoadedSchema:
    root = repo_root or Path.cwd()
    manifest_path = root / "resources" / "manifest.json"
    manifest = _load_manifest(manifest_path)

    schemas = manifest.get("schemas")
    if not isinstance(schemas, dict):
        raise ResourceLoaderError("resources.manifest missing 'schemas' object")
    schema_entry = schemas.get(name)
    if schema_entry is None:
        raise ResourceLoaderError(f"schema '{name}' not found in manifest")

    entries = _normalize_resource_entries("schema", name, schema_entry)
    enabled_entries = [entry for entry in entries if entry.get("enabled") is True]
    if len(enabled_entries) == 0:
        raise ResourceLoaderError(f"schema '{name}' has no enabled entry")
    if len(enabled_entries) > 1:
        raise ResourceLoaderError(f"schema '{name}' has multiple enabled entries")
    entry = enabled_entries[0]

    version = entry["version"]
    path_value = entry["path"]
    schema_path = _resolve_resource_path(path_value, root=root)
    if not schema_path.exists():
        raise ResourceLoaderError(f"schema file not found: {schema_path}")

    try:
        content = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResourceLoaderError(f"invalid schema json: {schema_path}") from exc
    if not isinstance(content, dict):
        raise ResourceLoaderError(f"schema root must be object: {schema_path}")

    raw_json = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return LoadedSchema(
        name=name,
        version=version,
        content=content,
        source_hash=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        path=str(schema_path),
    )


def load_enabled_template(name: str, *, repo_root: Path | None = None) -> LoadedTemplate:
    root = repo_root or Path.cwd()
    manifest_path = root / "resources" / "manifest.json"
    manifest = _load_manifest(manifest_path)

    templates = manifest.get("templates")
    if not isinstance(templates, dict):
        raise ResourceLoaderError("resources.manifest missing 'templates' object")
    template_entry = templates.get(name)
    if template_entry is None:
        raise ResourceLoaderError(f"template '{name}' not found in manifest")

    entries = _normalize_resource_entries("template", name, template_entry)
    enabled_entries = [entry for entry in entries if entry.get("enabled") is True]
    if len(enabled_entries) == 0:
        raise ResourceLoaderError(f"template '{name}' has no enabled entry")
    if len(enabled_entries) > 1:
        raise ResourceLoaderError(f"template '{name}' has multiple enabled entries")
    entry = enabled_entries[0]

    version = entry["version"]
    path_value = entry["path"]
    template_path = _resolve_resource_path(path_value, root=root)
    if not template_path.exists():
        raise ResourceLoaderError(f"template file not found: {template_path}")

    try:
        content = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResourceLoaderError(f"invalid template json: {template_path}") from exc
    if not isinstance(content, dict):
        raise ResourceLoaderError(f"template root must be object: {template_path}")

    raw_json = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return LoadedTemplate(
        name=name,
        version=version,
        content=content,
        source_hash=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        path=str(template_path),
    )


def load_enabled_policy(name: str, *, repo_root: Path | None = None) -> LoadedPolicy:
    root = repo_root or Path.cwd()
    try:
        manifest = _load_manifest(root / "resources" / "manifest.json")
    except ResourceLoaderError:
        return _fallback_policy(name)

    policies = manifest.get("policies")
    if not isinstance(policies, dict):
        return _fallback_policy(name)
    policy_entry = policies.get(name)
    if policy_entry is None:
        return _fallback_policy(name)

    try:
        entries = _normalize_resource_entries("policy", name, policy_entry)
        enabled_entries = [entry for entry in entries if entry.get("enabled") is True]
        if len(enabled_entries) != 1:
            return _fallback_policy(name)
        entry = enabled_entries[0]
        version = entry["version"]
        path_value = entry["path"]
        policy_path = _resolve_resource_path(path_value, root=root)
        if not policy_path.exists():
            return _fallback_policy(name)
        content = json.loads(policy_path.read_text(encoding="utf-8"))
        if not _is_valid_policy_content(name, content):
            return _fallback_policy(name)
    except (ResourceLoaderError, json.JSONDecodeError):
        return _fallback_policy(name)

    raw_json = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return LoadedPolicy(
        name=name,
        version=version,
        content=content,
        source_hash=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        path=str(policy_path),
        fallback=False,
    )


def _fallback_policy(name: str) -> LoadedPolicy:
    content = _builtin_policy_content(name)
    version = str(content.get("version", "builtin-v1"))
    raw_json = json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return LoadedPolicy(
        name=name,
        version=version,
        content=content,
        source_hash=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        path=f"builtin://policy/{name}",
        fallback=True,
    )


def _builtin_policy_content(name: str) -> Dict[str, Any]:
    if name == "turn_tool_policy":
        return {
            "id": "turn_tool_policy",
            "version": "builtin-v1",
            "tool_allowlist_default": [
                "move",
                "hp_delta",
                "inventory_add",
                "map_generate",
                "move_options",
                "world_generate",
                "actor_spawn",
                "scene_action",
            ],
            "retry_policy": {
                "max_conflict_retries": 2,
                "repeat_illegal_request_window": 3,
            },
            "conflict_policy": {
                "detector": "detect_conflicts",
                "text_checks_toggle_setting": "dialog.conflict_text_checks_enabled",
            },
            "notes": "metadata-only resource; runtime behavior still controlled by code.",
        }
    return {
        "id": name,
        "version": "builtin-v1",
        "notes": "metadata-only fallback policy descriptor.",
    }


def _is_valid_policy_content(name: str, content: object) -> bool:
    if not isinstance(content, dict):
        return False
    policy_id = content.get("id")
    version = content.get("version")
    if not isinstance(policy_id, str) or policy_id.strip() != name:
        return False
    if not isinstance(version, str) or not version.strip():
        return False
    if name != "turn_tool_policy":
        return True

    allowlist = content.get("tool_allowlist_default")
    if not isinstance(allowlist, list) or not all(
        isinstance(item, str) and item.strip() for item in allowlist
    ):
        return False
    if not isinstance(content.get("retry_policy"), dict):
        return False
    if not isinstance(content.get("conflict_policy"), dict):
        return False
    return True


def render_prompt(
    text: str, variables: Dict[str, str], allowlist: Iterable[str]
) -> str:
    if not isinstance(text, str) or not text:
        raise ResourceLoaderError("prompt text must be non-empty string")

    allowed = {key for key in allowlist if isinstance(key, str) and key}
    if not allowed:
        raise ResourceLoaderError("allowlist must contain at least one variable name")

    for key in variables.keys():
        if key not in allowed:
            raise ResourceLoaderError(f"prompt variable not allowed: {key}")

    rendered = text
    for key, value in variables.items():
        token = f"{{{{{key}}}}}"
        rendered = rendered.replace(token, value)

    unresolved = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", rendered))
    unresolved_allowed = [key for key in unresolved if key in allowed]
    if unresolved_allowed:
        missing = ", ".join(sorted(unresolved_allowed))
        raise ResourceLoaderError(f"prompt variables missing values: {missing}")

    return rendered


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ResourceLoaderError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResourceLoaderError(f"invalid manifest json: {path}") from exc
    if not isinstance(data, dict):
        raise ResourceLoaderError(f"manifest root must be object: {path}")
    return data


def _normalize_resource_entries(
    resource_kind: str, name: str, entry: object
) -> list[Dict[str, Any]]:
    if isinstance(entry, dict):
        entries = [entry]
    elif isinstance(entry, list):
        entries = entry
    else:
        raise ResourceLoaderError(
            f"{resource_kind} '{name}' must be object or list of objects in manifest"
        )
    normalized: list[Dict[str, Any]] = []
    for idx, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ResourceLoaderError(
                f"{resource_kind} '{name}' entry[{idx}] must be an object"
            )
        version = item.get("version")
        path_value = item.get("path")
        enabled = item.get("enabled")
        if not isinstance(version, str) or not version.strip():
            raise ResourceLoaderError(
                f"{resource_kind} '{name}' entry[{idx}] missing version"
            )
        if not isinstance(path_value, str) or not path_value.strip():
            raise ResourceLoaderError(
                f"{resource_kind} '{name}' entry[{idx}] missing path"
            )
        if not isinstance(enabled, bool):
            raise ResourceLoaderError(
                f"{resource_kind} '{name}' entry[{idx}] missing enabled bool"
            )
        normalized.append(
            {
                "version": version.strip(),
                "path": path_value.strip(),
                "enabled": enabled,
            }
        )
    return normalized


def _resolve_resource_path(path_value: str, *, root: Path) -> Path:
    resource_path = Path(path_value)
    if resource_path.is_absolute():
        raise ResourceLoaderError("resource path must be relative under resources/")
    if resource_path.parts and resource_path.parts[0] != "resources":
        raise ResourceLoaderError("resource path must start with resources/")
    if any(part == ".." for part in resource_path.parts):
        raise ResourceLoaderError("resource path must not include '..'")
    return root / resource_path
