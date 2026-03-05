from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_resources_payload(
    *,
    prompts: Optional[List[Dict[str, Any]]] = None,
    flows: Optional[List[Dict[str, Any]]] = None,
    schemas: Optional[List[Dict[str, Any]]] = None,
    templates: Optional[List[Dict[str, Any]]] = None,
    policies: Optional[List[Dict[str, Any]]] = None,
    template_usage: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "prompts": _clone_entries(prompts),
        "flows": _clone_entries(flows),
        "schemas": _clone_entries(schemas),
        "templates": _clone_entries(templates),
        "policies": _clone_entries(policies),
        "template_usage": _clone_entries(template_usage),
    }


def build_template_usage_debug(template_usage: Dict[str, Any]) -> Dict[str, Any]:
    usage = dict(template_usage) if isinstance(template_usage, dict) else {}
    return {
        "resources": build_resources_payload(template_usage=[usage]),
        # legacy compatibility field
        "template_usage": usage,
    }


def _clone_entries(entries: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    return [dict(item) for item in entries if isinstance(item, dict)]
