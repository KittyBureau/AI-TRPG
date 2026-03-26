from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the AI-TRPG backend from the repo root."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("AI_TRPG_HOST", "127.0.0.1"),
        help="Backend host. Default: 127.0.0.1 or AI_TRPG_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("AI_TRPG_PORT", "8000")),
        help="Backend port. Default: 8000 or AI_TRPG_PORT.",
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=_env_flag("AI_TRPG_RELOAD", True),
        help="Enable uvicorn reload mode (default on).",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable uvicorn reload mode.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    print(f"Repo root: {REPO_ROOT}")
    print(f"Storage root: {REPO_ROOT / 'storage'}")
    print(
        f"Starting backend at http://{args.host}:{args.port} "
        f"(reload={'on' if args.reload else 'off'})"
    )

    uvicorn.run(
        "backend.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
