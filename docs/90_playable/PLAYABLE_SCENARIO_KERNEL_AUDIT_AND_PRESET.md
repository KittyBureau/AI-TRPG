# Playable Scenario Kernel Audit + Handcrafted Preset

## 1. Alignment Summary

This note answers one question:

> Can the current AI-TRPG kernel support a small but genuinely engaging scenario, and what is the best preset shape within current limits?

Scope used for this audit:

- Read current turn loop, tool execution, scenario runtime mapping, campaign storage, map/view contract, and relevant tests.
- No core-model changes.
- No generator expansion.
- No watchtower behavior changes.

Primary evidence:

- `backend/app/turn_service.py`
- `backend/app/tool_executor.py`
- `backend/app/scenario_runtime_mapper.py`
- `backend/app/world_presets.py`
- `backend/api/routes/map.py`
- `backend/api/routes/campaign.py`
- `backend/tests/test_move_options.py`
- `backend/tests/test_scene_action_tool.py`
- `backend/tests/test_watchtower_world_turn_api.py`
- `backend/tests/test_scenario_runtime_integration.py`
- `backend/tests/test_map_view_scene_entities.py`

Validation run during this audit:

- `pytest backend/tests/test_move_options.py -q`
- `pytest backend/tests/test_scene_action_tool.py -q`
- `pytest backend/tests/test_watchtower_world_turn_api.py -q`
- `pytest backend/tests/test_scenario_runtime_integration.py -q`
- `pytest backend/tests/test_map_view_scene_entities.py -q`

All of the above passed.

## 2. Kernel Playability Audit

### A1. Supported Gameplay Loop

| Loop | Status | Why |
| --- | --- | --- |
| Exploration: `move` / `move_options` | `STABLE` | `move` enforces 1-hop adjacency, world/preset item gate checks, and goal-area completion; `move_options` is read-only and returns current 1-hop neighbors. Verified by `backend/app/tool_executor.py`, `backend/tests/test_move_options.py`, and watchtower/scenario runtime tests. |
| Interaction: `scene_action` | `WORKS_WITH_LIMITS` | The kernel supports `inspect`, `talk`, `open`, `search`, `take`, `drop`, `detach`, `use`, `wait`, with reachability and verb checks. But most actions resolve to static hint text, simple booleans, stack transfer, or lightweight patches rather than deep simulation. |
| Item loop: acquire -> store -> use | `WORKS_WITH_LIMITS` | Mainline `search -> reveal -> take` and inventory persistence are solid, and drop/use are real runtime actions. But `use` mostly toggles target `state.used` and optionally consumes the stack; it does not drive rich effect logic. |
| Gating: locked paths / conditions | `WORKS_WITH_LIMITS` | Item-gated movement exists, but it is authored in preset/scenario bridge logic rather than a generic runtime rule layer. Current hard gating is effectively "specific edge requires specific item." |
| Goal system: detectable completion | `WORKS_WITH_LIMITS` | Goal completion is reliable when mapped to entering a target area, and lifecycle end is marked consistently. Goal variety is narrow: current runtime end detection is mostly `enter_area` or party-death style outcomes. |

### A2. Realistic Play Experience Gaps

1. Hard progression is mostly single-item edge gating.
Why: `move` checks one required item id for one edge; there is no generic rule model for OR conditions, multi-step conditions, social clearance, or state-based gate formulas.
Type: `kernel limitation`

2. NPC interaction depth is shallow.
Why: `talk` succeeds cleanly, but practical output is a static hint-bearing entity plus model narration; there is no built-in dialogue state, trust, memory, bargaining, or unlock tree.
Type: `kernel limitation`

3. Item use has weak world consequence.
Why: `use` resolves selected inventory correctly, but the built-in effect is mainly "toggle target used" and optional item consumption.
Type: `kernel limitation`

4. Investigation chains are mostly authored as hint routing, not discovered facts.
Why: the runtime exposes area entities/items and supports search/talk, but it does not track explicit discovered clues, inference state, contradiction checks, or case logic.
Type: `kernel limitation`

5. Wrong actions have little systemic cost.
Why: failed `scene_action` calls usually return a truthful failure payload but do not create suspicion, noise, injury, lockout, or timer pressure. The only general pressure mechanic is milestone advancement, which is not tightly tied to scenario fiction.
Type: `kernel limitation`

6. Persistent consequence is narrow.
Why: durable state exists for positions, actor hp/state, item ownership, and entity booleans, but not for social relationships, area alertness, scene contamination, witness reactions, or partial puzzle progress.
Type: `kernel limitation`

7. Alternative solutions are possible only in a soft-authored sense.
Why: a preset can author multiple clue sources or multiple item sources, but the kernel does not yet offer a clean abstraction for "any of these facts/items satisfy this gate."
Type: `kernel limitation`

8. Search realism is binary and deterministic.
Why: searchable content is typically a single revealed stack or a static "nothing useful" response. There is no hidden-depth model, partial search quality, or noisy evidence.
Type: `content/preset limitation` with current kernel pressure

9. Goal payoff can feel gamey if the scenario climax is not spatial.
Why: the runtime can detect "entered target area" very well, but it does not yet natively score accusation, proof assembly, negotiation success, or escape clock resolution.
Type: `kernel limitation`

10. Large authored scenarios will likely feel thin rather than rich.
Why: current scenario metadata template is small, prompt context is broad but not deeply structured, and the runtime lacks enough abstractions to keep many areas/entities mutually reactive.
Type: `kernel limitation`

### A3. Kernel Sufficiency Conclusion

Yes: the current kernel is sufficient for a **small, hand-authored, convincing TRPG-like scenario** if the design leans on:

- movement between a few clearly connected areas
- talk/search/inspect as the main progression verbs
- portable item reveal/take as the main tangible reward loop
- one clear spatial end condition
- soft investigation branching instead of deep systemic simulation

Safe scale for now:

- Area count: `5-7` authored areas is the safest range.
- Interactive entities: about `8-14` meaningful entities total.
- NPCs: `2-3`.
- Portable items: `1-3` key items.
- Branching: `1` mainline, `1` optional branch, and at most `2` alternate clue or item-acquisition routes.

What must be avoided for now:

- stealth/infiltration systems that need alertness or patrol state
- combat-heavy scenarios
- puzzles that require multi-condition rule solving
- social negotiation that depends on relationship tracking
- failure loops that need clocks, suspicion, or escalating scene response
- endings that depend on anything more abstract than "reach target area" unless handled almost entirely by authored narration

## 3. Scenario Type Selection + Justification

Chosen type: `investigation`

Why this fits best:

- The current kernel is strongest at `talk`, `inspect`, `search`, `take`, and `move`.
- Investigation can feel believable with mostly soft information gates plus one or two item-gated movement checks.
- Infiltration would expose missing alert/stealth systems too quickly.
- Escape would want stronger pressure, countdowns, and failure costs than the current kernel actually enforces.

## 4. Scenario Blueprint

### Basic Info

- Title: `Midnight Archive`
- Theme: `rain-soaked civic archive, forged records, locked back room`
- Player goal: `Get into the restricted archive before dawn and confirm where the forged inspection file was hidden.`
- Optional secondary goal: `Learn who falsified the file and why.`

### Map Structure

Areas: `6`

- `street_gate`
- `lobby`
- `reading_room`
- `clerk_office`
- `storage_room`
- `restricted_archive`

Adjacency graph:

- `street_gate <-> lobby`
- `lobby <-> reading_room`
- `lobby <-> clerk_office`
- `reading_room <-> storage_room`
- `clerk_office <-> storage_room`
- `storage_room <-> restricted_archive`

Intended gate placement:

- `lobby -> clerk_office` requires `office_pass`
- `storage_room -> restricted_archive` requires `archive_key`

### Entities

`street_gate`

- `porter_npc`
  - interactive: `yes`
  - searchable: `no`
  - gate-related: `soft clue gate`

`lobby`

- `notice_board`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `soft clue gate`
- `lost_and_found_tray`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `reveals office_pass`
- `office_door`
  - interactive: `yes`
  - searchable: `no`
  - gate-related: `hard gate for clerk_office move`

`reading_room`

- `assistant_archivist_npc`
  - interactive: `yes`
  - searchable: `no`
  - gate-related: `soft clue gate`
- `returns_cart`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `reveals inspection_note`
- `donation_box`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `optional alternate archive_key source`

`clerk_office`

- `desk_safe`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `main archive_key source`
- `shift_ledger`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `soft clue gate`

`storage_room`

- `janitor_npc`
  - interactive: `yes`
  - searchable: `no`
  - gate-related: `optional info branch`
- `archive_door`
  - interactive: `yes`
  - searchable: `no`
  - gate-related: `hard gate for restricted_archive move`

`restricted_archive`

- `forged_file_shelf`
  - interactive: `yes`
  - searchable: `yes`
  - gate-related: `goal flavor, post-entry payoff`

### NPCs

1. `porter_npc`
- Role: tired night porter at the front gate
- Information: the duty clerk panicked after midnight and kept checking the lobby tray and office door
- Condition to unlock info: available immediately; extra useful once the player inspects the notice board or asks about the file

2. `assistant_archivist_npc`
- Role: last honest staff member still in the reading room
- Information: there is a spare archive key somewhere among returned donations, and the clerk hid the real file in the back archive
- Condition to unlock info: best after the player reaches `reading_room`; can be further reinforced if the player has already found `inspection_note`

3. `janitor_npc`
- Role: maintenance worker in the storage room
- Information: the forged stamp came from the clerk office, which confirms motive and provides optional extra story payoff
- Condition to unlock info: accessible after reaching `storage_room`; more revealing if the player already searched `shift_ledger` or carries `inspection_note`

### Items

1. `office_pass`
- How to obtain: search `lost_and_found_tray`
- How used: satisfies the `lobby -> clerk_office` move gate

2. `archive_key`
- How to obtain: either search `desk_safe` in `clerk_office` or search `donation_box` in `reading_room`
- How used: satisfies the `storage_room -> restricted_archive` move gate

3. `inspection_note`
- How to obtain: search `returns_cart`
- How used: not as a hard mechanic; it strengthens the investigation chain and optional NPC revelations

### Gating Design

Gate 1: `clerk office access`

- Hard gate: `lobby -> clerk_office` requires `office_pass`
- Purpose: makes the office route feel earned instead of free
- Progress options:
  - talk to `porter_npc` then search `lost_and_found_tray`
  - inspect/search `notice_board` then search `lost_and_found_tray`

Gate 2: `restricted archive access`

- Hard gate: `storage_room -> restricted_archive` requires `archive_key`
- Purpose: creates a believable final locked-space climax
- Progress options:
  - office route: get `office_pass`, enter `clerk_office`, search `desk_safe`, take `archive_key`
  - reading-room route: search `donation_box`, take spare `archive_key`, bypass office entirely

This gives two real progression routes:

- `Lobby -> Clerk Office -> Storage Room -> Restricted Archive`
- `Lobby -> Reading Room -> Storage Room -> Restricted Archive`

### Information Chain

What to do first:

- `porter_npc` and `notice_board` both point the player toward the clerk and the tray/office angle

Where to go next:

- `assistant_archivist_npc` and `returns_cart` point toward either the donation box spare key or the fact that the real file is in the back archive

How to understand the climax:

- `shift_ledger`, `janitor_npc`, and `forged_file_shelf` confirm that the archive room matters and that the forged file was hidden there on purpose

### Optional Branch

Optional path: `reading_room -> returns_cart`

- Reward: `inspection_note`
- Benefit: richer explanation of the forgery and better NPC payoff from `janitor_npc`
- Why it fits now: this is an information reward, not a mechanic the kernel cannot represent

### Failure / Cost Design

If the player chooses a wrong interaction:

- Cost: mostly wasted turns and truthful "nothing useful" feedback
- Runtime reality: current kernel does not enforce suspicion or alarms here

If the player delays:

- Cost: milestone progression advances quietly in the background, which can be narrated as dawn pressure
- Runtime reality: this is soft pressure, not a scenario-specific countdown

If the player misuses an item:

- Cost: keep misuse low-stakes or optional only
- Runtime reality: `use` exists, but central progression should not depend on it because current effect semantics are too thin

## 5. Kernel Mapping Explanation

Why this preset fits the current kernel:

- Area travel maps directly onto `move` and `move_options`.
- Soft clueing maps onto `scene_action talk`, `inspect`, and `search`.
- Portable evidence and keys map onto stack-backed item reveal plus `scene_action take`.
- Area-local scene presentation maps cleanly to `/api/v1/map/view`, which already projects both entities and revealed area-root item stacks.
- Goal closure maps to entering `restricted_archive`, which matches the runtime's strongest completion path.

Why it should feel better than watchtower:

- It has two meaningful routes instead of one straight key-door line.
- It uses two NPCs plus one optional NPC for layered clue delivery.
- It separates "learn the situation" from "obtain the key" from "reach the locked room."
- It creates one optional evidence branch, so not every successful run looks identical.
- It stays inside existing mechanics instead of pretending the runtime can support deeper stealth/combat/social systems than it really can.

## 6. Generator Gap Analysis

### C1. What can already be generalized into a generator

- Small area graph with named structural roles
- Start area, clue area, gated area, target area pattern
- Searchable clue source that reveals a portable item stack
- NPC hint source with static or lightly conditional clue text
- Move-gated target entry
- Optional branch that awards extra clue text instead of new mechanics
- Hand-authored "two paths to same destination" topology

### C2. What cannot yet be generated reliably

- Conditional NPC dialogue trees
- Rich evidence logic or contradiction-based investigation
- Gates that support OR logic, multi-item logic, or state formulas
- Strong failure consequences such as suspicion, alarms, or scene escalation
- Endings based on accusation, proof submission, or negotiation
- Multi-step item effects where `use` changes traversal rules or scenario truth in a robust way

### C3. Minimal future extensions

- Data-driven gate rules in world/scenario data instead of preset code branches
- Goal rules beyond `enter_area`
- Lightweight discovered-facts or clue-state tracking
- Conditional NPC info phases
- Small scenario clock or alert meter
- Structured interaction effects for `use`, `open`, and `search`
- Support for multiple valid gate satisfiers

## 7. Minimal TODO

- Add one new handcrafted preset world using the above archive investigation shape.
- Keep goal completion spatial: enter the final archive room.
- Author two hard move gates only if implemented preset-side; do not expand the core data model yet.
- Keep NPC info mostly static or lightly state-aware through existing prompt context.
- Do not push this design into the generator until data-driven gates, clue state, and broader goal rules exist.
