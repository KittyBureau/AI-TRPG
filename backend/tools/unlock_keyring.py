from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from getpass import getpass
from typing import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unlock the backend keyring for the running AI-TRPG server."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL. Default: http://127.0.0.1:8000",
    )
    return parser


def _post_unlock(base_url: str, passphrase: str) -> tuple[int, dict | None, str]:
    payload = json.dumps({"passphrase": passphrase}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/runtime/unlock",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = None
        return exc.code, data, body


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    passphrase = getpass("Enter keyring passphrase: ")
    if not passphrase:
        print("Unlock failed: empty passphrase.", file=sys.stderr)
        return 1

    try:
        status_code, data, raw = _post_unlock(args.base_url, passphrase)
    except urllib.error.URLError as exc:
        print(
            f"Unlock failed: cannot reach backend at {args.base_url} ({exc.reason}).",
            file=sys.stderr,
        )
        return 1

    if status_code == 200 and isinstance(data, dict) and data.get("ready") is True:
        print("Unlock succeeded. Runtime status is ready=true.")
        return 0

    reason = None
    if isinstance(data, dict):
        reason = data.get("reason")
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            reason = detail.strip()
    reason = reason or raw or f"HTTP {status_code}"
    print(f"Unlock failed: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
