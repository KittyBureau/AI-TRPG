# State Machine (Stage 3)

## States

- `alive`
- `dying`
- `unconscious`
- `restrained_permanent`
- `dead`

## Rules

- `dying`: no actions except `hp_delta` with positive `delta` on the actor.
- `unconscious`: no tool execution.
- `restrained_permanent` and `dead`: no tool execution.
- `alive`: tools may execute if allowed by allowlist.
- Movement position changes require tool execution (move); narration alone does not move characters.

`rules.hp_zero_ends_game`:

- If enabled and HP becomes `<= 0`, set state to `dying`.
- If HP rises above `0` from `dying`, restore to `alive`.

State is persisted in `campaign.json` under `character_states`.

## Tool Decision Matrix

| State | move | move_options | hp_delta | map_generate |
| --- | --- | --- | --- | --- |
| alive | allow | allow | allow | allow |
| dying | reject | reject | allow if delta > 0 on actor | reject |
| unconscious | reject | reject | reject | reject |
| restrained_permanent | reject | reject | reject | reject |
| dead | reject | reject | reject | reject |
