from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LLMProfile:
    name: str
    base_url: str
    model: str
    temperature: float
    api_key_ref: str
    timeout_sec: int = 30
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None


def get_llm_config_path() -> Path:
    return Path.cwd() / "storage" / "config" / "llm_config.json"


def load_llm_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path or get_llm_config_path()
    if not path.exists():
        raise FileNotFoundError(f"LLM config file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"LLM config root must be an object: {path}")
    return data


def get_active_profile(
    config: Dict[str, Any], config_path: Optional[Path] = None
) -> LLMProfile:
    path = config_path or get_llm_config_path()
    current = config.get("current_profile")
    if not isinstance(current, str) or not current.strip():
        raise ValueError(f"LLM config missing current_profile: {path}")
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError(f"LLM config missing profiles map: {path}")
    profile = profiles.get(current)
    if not isinstance(profile, dict):
        raise ValueError(f"LLM profile not found: {current}")
    return _parse_profile(current, profile, path)


def set_current_profile(
    profile_name: str, config_path: Optional[Path] = None
) -> None:
    path = config_path or get_llm_config_path()
    config = load_llm_config(path)
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict) or profile_name not in profiles:
        raise ValueError(f"LLM profile not found: {profile_name}")
    config["current_profile"] = profile_name
    _atomic_write(path, config)


def _parse_profile(name: str, data: Dict[str, Any], path: Path) -> LLMProfile:
    base_url = _require_str(data, "base_url", path, name)
    model = _require_str(data, "model", path, name)
    api_key_ref = _require_str(data, "api_key_ref", path, name)
    temperature = _require_number(data, "temperature", path, name)
    timeout_sec = _optional_int(data, "timeout_sec", default=30)
    max_tokens = _optional_int(data, "max_tokens", default=None)
    response_format = data.get("response_format")
    if response_format is not None and not isinstance(response_format, dict):
        raise ValueError(f"LLM profile {name} response_format must be an object: {path}")
    return LLMProfile(
        name=name,
        base_url=base_url,
        model=model,
        temperature=temperature,
        api_key_ref=api_key_ref,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        response_format=response_format,
    )


def _require_str(data: Dict[str, Any], key: str, path: Path, name: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM profile {name} missing {key}: {path}")
    return value


def _require_number(data: Dict[str, Any], key: str, path: Path, name: str) -> float:
    value = data.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"LLM profile {name} missing {key}: {path}")


def _optional_int(
    data: Dict[str, Any], key: str, default: Optional[int]
) -> Optional[int]:
    value = data.get(key, default)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ValueError(f"LLM profile {key} must be int if provided")


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    if not path.parent.exists():
        raise FileNotFoundError(f"LLM config directory missing: {path.parent}")
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)
