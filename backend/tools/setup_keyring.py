from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

from backend.services.keyring import describe_keyring_requirement, ensure_key_exists, get_keyring_path
from backend.services.llm_config import get_active_profile, get_llm_config_path, load_llm_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or populate the local AI-TRPG keyring for the active LLM profile."
    )
    parser.add_argument(
        "--skip-copy-config",
        action="store_true",
        help=(
            "Fail instead of copying storage/config/llm_config.example.json "
            "to llm_config.json when the config file is missing."
        ),
    )
    return parser


def _require_repo_root() -> None:
    cwd = Path.cwd()
    if not (cwd / "backend").exists() or not (cwd / "README.md").exists():
        raise RuntimeError(
            "Run this command from the repository root so storage/ resolves correctly."
        )


def _ensure_config_exists(*, skip_copy: bool) -> tuple[Path, bool]:
    config_path = get_llm_config_path()
    if config_path.exists():
        return config_path, False

    example_path = config_path.with_name("llm_config.example.json")
    if skip_copy:
        raise FileNotFoundError(f"LLM config file not found: {config_path}")
    if not example_path.exists():
        raise FileNotFoundError(
            f"LLM config example file not found: {example_path}"
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, config_path)
    return config_path, True


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _require_repo_root()
        config_path, copied_config = _ensure_config_exists(
            skip_copy=args.skip_copy_config
        )
        config = load_llm_config(config_path)
        profile = get_active_profile(config, config_path)
        previous_state = describe_keyring_requirement(profile.api_key_ref)
        ensure_key_exists(profile.api_key_ref)
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1

    if copied_config:
        print(f"Created {config_path} from the example config.")
    print(
        f"Active profile: {profile.name} (api_key_ref={profile.api_key_ref}, model={profile.model})"
    )
    print(f"Keyring path: {get_keyring_path()}")
    if previous_state in {"passphrase_required", "ready"}:
        print("Keyring entry already existed for the active profile.")
    else:
        print("Keyring entry is now initialized for the active profile.")
    print("Next steps:")
    print("1. Start the backend from the repo root.")
    print("2. If runtime status says passphrase_required, run:")
    print("   python -m backend.tools.unlock_keyring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
