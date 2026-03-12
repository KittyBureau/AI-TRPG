# Scenario World Panel Smoke

## Scope

This smoke verifies the minimal frontend path for scenario-backed world generation through
the existing `play.html` World Panel.

Out of scope:

- advanced scenario editing
- scenario previews
- new pages or editors
- watchtower preset regression details

## Preconditions

1. Backend is running at `http://127.0.0.1:8000`.
2. Frontend static server is running and `play.html` is open.
3. At least one character is available in the Character Library Panel.

## Generate Scenario World

1. Open **World Panel**.
2. Set `Mode` to `Scenario-backed`.
3. Enter a new `World ID`, for example `world_ui_scenario_smoke`.
4. Keep or set:
   - `Template = Key Gate Scenario`
   - `Theme = watchtower`
   - `Area Count = 6`
   - `Layout = Branch`
   - `Difficulty = Easy`
5. Click `Generate World`.

Expected results:

- status line reports the world was created or normalized
- world list now includes the new world id
- world list row shows `scenario-backed`

## Create Campaign

1. Open **Campaign Panel**.
2. Create a campaign using the generated world id.
3. Load at least one character into the campaign if needed.
4. Confirm the campaign refresh succeeds.

Expected results:

- campaign creation succeeds without manual JSON edits
- current campaign world is the generated scenario world
- actor starts in `area_start`

## Playable Flow

1. Use the current play controls to interact with the hint source in the start area.
2. Move to `area_clue`.
3. Search the clue source.
4. Confirm the key item is added.
5. Move to `area_gate`.
6. Enter `area_target`.

Expected results:

- hint interaction is available
- searchable clue source grants the required item once
- gated progression blocks target entry before key acquisition
- target entry succeeds after key acquisition
- campaign ends with `goal_achieved`

## Pass Criteria

1. Scenario-backed world generation is reachable from the existing World Panel.
2. Generated world appears in the normal world list with lightweight scenario labeling.
3. Campaign creation works with that world id.
4. Existing play flow completes the key-gate scenario without backend or frontend special handling.
5. Watchtower remains available as the separate hand-authored regression baseline.
