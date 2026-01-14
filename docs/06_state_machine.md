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

`rules.hp_zero_ends_game`:

- If enabled and HP becomes `<= 0`, set state to `dying`.
- If HP rises above `0` from `dying`, restore to `alive`.

State is persisted in `campaign.json` under `character_states`.

## Tool Decision Matrix

| State | move | hp_delta | map_generate |
| --- | --- | --- | --- |
| alive | allow | allow | allow |
| dying | reject | allow if delta > 0 on actor | reject |
| unconscious | reject | reject | reject |
| restrained_permanent | reject | reject | reject |
| dead | reject | reject | reject |
