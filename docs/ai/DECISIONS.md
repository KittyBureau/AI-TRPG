# Decisions

## Default decisions
1) Data placement
- Decision: Keep versioned sample/fixture data in `codes/backend/storage/`.
- Rationale: Git-tracked, reproducible, and separated from local runtime outputs.
- Status: default (待确认 by owner).

2) Service boundaries
- Decision: API layer stays thin; logic lives in `codes/backend/services/`.
- Rationale: Easier testing and reuse across endpoints.
- Status: default (待确认 by owner).

3) API validation and errors
- Decision: New endpoints must validate input with Pydantic models and return `status/message` JSON on errors.
- Rationale: Consistent client behavior and debuggability.
- Status: default (待确认 by owner).

4) Movement path identity
- Decision: Use signature-style `path_id` (e.g., `loc_a->loc_b->loc_c`).
- Rationale: Deterministic IDs support re-validation in `apply_move`.
- Status: default (待确认 by owner).
