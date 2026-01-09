# Dialog Routing Test Method

## Goal
Validate dialog routing decisions, context profile selection, block inclusion/exclusion, and guard behavior without modifying business logic.

## Preconditions
- `config.json` includes `dialog_routes` and `context_profiles` (copy from `backend/storage/config_template.json` if needed).
- Ensure `rules_text_path` is set in `%USERPROFILE%\.ai-trpg\config.json` if validating rules-only output.
- If testing `character_state`/`lore` blocks, set `character_state_path` / `lore_path` to readable files or directories.
- The repository root is the working directory for commands below.

## Method A: Offline message assembly (no LLM call)
Run the snippet below to inspect the message list assembled for each route profile.

```python
from backend.services import context_builder, context_config, conversation_store, dialog_router

config = context_config.load_context_config()

conversation = conversation_store.create_conversation()
conversation["summary"] = {"summary_note": "summary-test"}
conversation["key_facts"] = ["fact-a", "fact-b"]
conversation["messages"] = [
    conversation_store.new_message("user", "U1"),
    conversation_store.new_message("assistant", "A1"),
    conversation_store.new_message("user", "U2"),
    conversation_store.new_message("assistant", "A2"),
    conversation_store.new_message("user", "U3"),
    conversation_store.new_message("assistant", "A3"),
]

routes = [
    ("narrative", "scene_pure"),
    ("narrative", "scene_general"),
    ("action_intent", "light"),
    ("rules_query", "explain"),
]

for dialog_type, variant in routes:
    route = dialog_router.resolve_dialog_route(
        config=config,
        dialog_type=dialog_type,
        variant=variant,
        context_profile=None,
        response_style=None,
        guards=None,
    )
    profile = config.context_profiles[route.context_profile]
    messages = context_builder.build_messages(
        conversation=conversation,
        user_text="test-input",
        config=config,
        route=route,
        profile=profile,
        mode=None,
        context_strategy=None,
        persona_lock_enabled=True,
    )
    print("\n==", dialog_type, variant, "=>", route.context_profile)
    for msg in messages:
        preview = msg["content"].replace("\n", " ")[:80]
        print(f"{msg['role']}: {preview}")
```

Expected checks:
- `rules_query.explain` only includes the rules block (no history, no key facts, no character/world state) when profile strategy is `compact_context`.
- `narrative.scene_pure` excludes character sheet/rules text.
- `narrative.scene_general` and `action_intent.light` include character_state/world_state when paths exist.
- `recent_turns_n` limits history only when `context_strategy` resolves to `compact_context`.

Note: `conversation_store.create_conversation()` writes a file under `backend/data/conversations/`. Remove it after testing if needed.

## Method B: API-level routing check (requires LLM access)
1) Start the server:

```powershell
cd e:\202410\Repos\DocumentsAndDirectives
python -m uvicorn backend.app.main:app --reload
```

2) Call `/api/chat/send` with explicit routing fields (UTF-8 safe):

```powershell
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8

$body = @{
  user_text = "Explain the rules only."
  dialog_type = "rules_query"
  variant = "explain"
  response_style = "default"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/chat/send `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

3) Inspect the conversation file under `backend/data/conversations/` and verify:
- `meta.dialog_route.dialog_type`, `variant`, and `context_profile` match the request.
- `meta.dialog_route.context_strategy` matches the resolved profile strategy.
- `meta.dialog_route.guards` reflects the guard list (default or overridden).

Expected checks:
- The response is produced and conversation metadata records the resolved route.

## Pass Criteria
- Route resolution returns the expected `context_profile` for all four V0 routes.
- Profile block inclusion matches the design rules in `docs/design/dialog_routing.md`.
- Guards are present in `meta.dialog_route.guards` and persona lock is applied when triggered.

## Optional: Compact Context Spot Check
- Set `context_strategy` to `compact_context` (request override or profile).
- Expect `character_sheet` to include only highlight fields (id/name/motivation/strengths/flaw/weaknesses, etc.).
- Expect `world_state` to include summary fields or a compact structure (time, ids, counts).
- Expect `recent_turns` only when the profile includes it and does not exclude it.
