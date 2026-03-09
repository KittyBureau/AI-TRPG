from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


_ITEM_CATALOG_RELATIVE_PATH = Path("resources") / "data" / "items_catalog_v1.json"


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def load_item_catalog(repo_root: Path | None = None) -> Dict[str, Dict[str, str]]:
    root = repo_root or Path.cwd()
    catalog_path = root / _ITEM_CATALOG_RELATIVE_PATH
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    catalog: Dict[str, Dict[str, str]] = {}
    for raw_item_id, raw_entry in raw.items():
        item_id = _normalize_text(raw_item_id)
        if not item_id or not isinstance(raw_entry, dict):
            continue
        normalized_entry: Dict[str, str] = {}
        name = _normalize_text(raw_entry.get("name"))
        description = _normalize_text(raw_entry.get("description"))
        if name:
            normalized_entry["name"] = name
        if description:
            normalized_entry["description"] = description
        if normalized_entry:
            catalog[item_id] = normalized_entry
    return catalog
