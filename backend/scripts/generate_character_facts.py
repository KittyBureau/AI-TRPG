from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.character_fact_generation import (
    CharacterFactGenerationRequest,
    CharacterFactGenerationService,
)
from backend.infra.file_repo import FileRepo


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist CharacterFact drafts into batch+individual generated files.",
    )
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--drafts-json", required=True, help="Path to JSON array file")
    parser.add_argument("--storage-root", default="storage")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--max-count", type=int, default=20)
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--id-policy", default="system")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    drafts_path = Path(args.drafts_json)
    raw = json.loads(drafts_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("drafts-json must be a JSON array")

    repo = FileRepo(Path(args.storage_root))
    service = CharacterFactGenerationService(repo)
    request = CharacterFactGenerationRequest(
        campaign_id=args.campaign_id,
        request_id=args.request_id,
        language=args.language,
        count=args.count,
        max_count=args.max_count,
        id_policy=args.id_policy,
    )
    result = service.persist_generated_batch(request, raw)

    output = {
        "batch_path": result.batch_path,
        "individual_paths": result.individual_paths,
        "count": len(result.items),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
