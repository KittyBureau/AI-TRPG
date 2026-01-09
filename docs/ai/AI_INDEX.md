# AI Index

This directory provides a minimal index for AI-related documentation and coding standards.

## Core docs
- `docs/ai/CONVENTIONS.md` - Directory, naming, logging, config, and data placement rules.
- `docs/ai/ARCHITECTURE.md` - Current layering and module boundaries.
- `docs/ai/DECISIONS.md` - Default decisions (with rationale).
- `docs/ai/CHECKLIST.md` - Pre-submit checks (format/lint/type/test).
- `docs/ai/CHANGELOG_AI.md` - AI documentation change log.

## Project docs
- `docs/ai-trpg/README.md` - AI-TRPG document index.
- `docs/ai-trpg/specs/tool_spec.md` - Tooling protocol and backend design.
- `docs/ai-trpg/specs/world_space_and_movement_spec.md` - Movement system spec.
- `docs/ai-trpg/project/world_space_and_movement_implementation.md` - Implementation notes.

## Design docs
- `docs/design/dialog_routing.md` - Dialog routing and context profile specification.

## Test docs
- `docs/testing/dialog_routing_test_method.md` - Dialog routing test procedures.

## Prompts
- `docs/ai/CODE_REVIEW_PROMPT.md` - Codex prompt for generating periodic code review docs.

## Update rules
- Keep entries short and stable; expand details in the target document.
- Required before context work: read `docs/TODO_CONTEXT.md`.
- Human-only onboarding docs live in `docs/human/` (e.g. `docs/human/LEARNING_PATH.md`) and should be skipped unless explicitly requested.
- If an item is uncertain, mark it as "???" and propose a default.
