# Midnight Archive Experience Upgrade

## 1. Alignment Summary

- No kernel changes.
- No new systems.
- No tool contract changes.
- No persistence changes.
- Upgrade approach: preset-only redesign using map shape, entity roles, item roles, NPC hint staging, and prompt-level soft-reactivity.

This upgrade keeps the current runtime assumptions:

- movement stays `move` / `move_options`
- interaction stays `scene_action`
- portable progression stays `search -> reveal -> take`
- hard runtime gating stays item-based on selected map edges
- perceived reactivity comes from prompt/context and authored clue routing, not new backend logic

## 2. Upgrade Strategy

### What is wrong with the original design

The original `Midnight Archive` works, but it still feels too close to:

- find the right key
- open the right route
- enter the final room

Its main weakness is not lack of functionality. It is lack of leverage:

- information mostly confirms what the player already needs to do
- the “best” route is too obvious
- alternate content is mostly flavor
- delay has little felt effect

### What changes conceptually

The redesign shifts:

- from `item gating` to `information-influenced routing`
- from `linear discovery` to `branching discovery`
- from `one correct sequence` to `two viable approaches`

The core trick is a preset-side pseudo OR-gate:

- Path A: the official route, which still uses item gating
- Path B: the service route, which bypasses the official gate but depends on actionable information

This does not create a true runtime OR-rule. It creates a **story OR-gate**:

- the same progression point, “reach the restricted archive,” can be solved by two different authored routes
- one is key-based
- one is clue-based

That keeps the kernel unchanged while making information materially affect play.

## 3. Enhanced Scenario Blueprint

### Basic Info

- Title: `Midnight Archive`
- Theme: `rain-soaked municipal archive on the night before an inspection cover-up collapses`
- Player goal: `Reach the restricted archive and recover proof that the inspection record was falsified.`
- Optional secondary goal: `Learn whether the forgery was panic, corruption, or coercion.`

### Map Structure

Areas: `7`

- `street_gate`
- `lobby`
- `reading_room`
- `returns_annex`
- `clerk_office`
- `storage_room`
- `restricted_archive`

Connections:

- `street_gate <-> lobby`
- `lobby <-> reading_room`
- `lobby <-> clerk_office`
- `reading_room <-> returns_annex`
- `clerk_office <-> storage_room`
- `returns_annex <-> storage_room`
- `storage_room <-> restricted_archive`
- `returns_annex <-> restricted_archive`

Design intent:

- `storage_room -> restricted_archive` is the official locked route
- `returns_annex -> restricted_archive` is the service bypass route
- both routes reach the same final progression point

### Entities

#### `street_gate`

- `porter_npc`
  - provides info: `yes`
  - provides alternative path: `indirectly`
  - role: first impression, official-route framing

#### `lobby`

- `notice_board`
  - provides info: `yes`
  - provides alternative path: `no`
  - role: shows archive workflow, clerk panic, and returns timing
- `lost_and_found_tray`
  - provides info: `no`
  - provides alternative path: `yes`
  - role: reveals `office_pass`
- `duty_roster`
  - provides info: `yes`
  - provides alternative path: `indirectly`
  - role: points to who is trustworthy and who is hiding something

#### `reading_room`

- `assistant_archivist_npc`
  - provides info: `yes`
  - provides alternative path: `yes`
  - role: strongest service-route guide
- `returns_cart`
  - provides info: `yes`
  - provides alternative path: `yes`
  - role: reveals `routing_slip`
- `reference_index`
  - provides info: `yes`
  - provides alternative path: `indirectly`
  - role: confirms restricted archive shelf code

#### `returns_annex`

- `document_lift`
  - provides info: `yes`
  - provides alternative path: `yes`
  - role: service-route entry point into the archive
- `sealed_crate`
  - provides info: `yes`
  - provides alternative path: `no`
  - role: optional branch clue that changes NPC interpretation later

#### `clerk_office`

- `desk_safe`
  - provides info: `no`
  - provides alternative path: `yes`
  - role: reveals `archive_key`
- `shift_ledger`
  - provides info: `yes`
  - provides alternative path: `indirectly`
  - role: shows that records were moved after hours
- `burn_basin`
  - provides info: `yes`
  - provides alternative path: `no`
  - role: optional evidence that someone tried to destroy drafts

#### `storage_room`

- `janitor_npc`
  - provides info: `yes`
  - provides alternative path: `yes`
  - role: confirms which route is safer or more urgent
- `archive_door`
  - provides info: `no`
  - provides alternative path: `no`
  - role: official locked gate

#### `restricted_archive`

- `forged_file_shelf`
  - provides info: `yes`
  - provides alternative path: `goal payoff`
  - role: objective target

### NPCs

#### 1. `porter_npc`

- Initial line:
  - “If you are here for the inspection records, you are late. The duty clerk has been guarding his office like a drowning man guards a plank.”
- After player finds a clue:
  - If player has `office_pass`: “Then you already know the clerk dropped something in his hurry. Use it before he notices what is missing.”
  - If player has `routing_slip`: “So you found the returns routing. Then do not bother with the office unless you want trouble.”
- After player asks a specific question:
  - Ask about clerk: points toward `clerk_office`
  - Ask about returns: reluctantly mentions late-night document transfers
- Unique value:
  - Frames the official route as obvious but risky, and the service route as unofficial once the player has proof it exists

#### 2. `assistant_archivist_npc`

- Initial line:
  - “The official cabinets are locked, but records do not always travel by official means.”
- After player finds a clue:
  - If player has `routing_slip`: clearly explains that the returns lift from `returns_annex` reaches archive shelving
  - If player has `inspection_note` or burned draft evidence: becomes more confident that the forgery was deliberate
- After player asks a specific question:
  - Ask where the real file is: points to `restricted_archive`
  - Ask how records move after hours: points to `returns_annex` and `document_lift`
- Unique value:
  - Provides the clearest information-driven alternative path

#### 3. `janitor_npc`

- Initial line:
  - “If you are headed for that archive door, bring a key or a better idea.”
- After player finds a clue:
  - If player has `archive_key`: confirms official route is fast
  - If player has `routing_slip`: confirms the lift route is quieter and bypasses the door
  - If player has optional evidence from `sealed_crate` or `burn_basin`: suggests the clerk was covering for someone else
- After player asks a specific question:
  - Ask about the door: confirms it is truly locked
  - Ask about service movement: confirms carts and lift traffic from `returns_annex`
- Unique value:
  - Validates whichever route the player is considering and reduces uncertainty

### Items

#### 1. `office_pass`

- Obtain: search `lost_and_found_tray`
- Mandatory: `no`
- Function:
  - enables official route into `clerk_office`
  - supports the office-first playstyle

#### 2. `archive_key`

- Obtain: search `desk_safe`
- Mandatory: `no`
- Function:
  - enables official route from `storage_room` to `restricted_archive`
  - fastest hard-confirmed route once obtained

#### 3. `routing_slip`

- Obtain: search `returns_cart`
- Mandatory: `no`
- Function:
  - reveals that `returns_annex -> restricted_archive` is a valid bypass route
  - actionable information item, not just lore

#### 4. `inspection_note`

- Obtain: search `sealed_crate` or `burn_basin`
- Mandatory: `no`
- Function:
  - does not open a gate
  - changes later NPC confidence and clarity
  - strengthens the player’s understanding of motive

### Gating Design

#### Gate 1: “Get a viable route into the back archive system”

This is a conceptual gate, not a new runtime gate type.

##### Path A: official route

- search `lost_and_found_tray`
- take `office_pass`
- move from `lobby` to `clerk_office`
- search `shift_ledger` and `desk_safe`

Why it works:

- supported by normal `search -> take -> move`
- office access is tangible and clear

##### Path B: information-driven route

- talk to `assistant_archivist_npc` or inspect `notice_board`
- search `returns_cart`
- take `routing_slip`
- move to `returns_annex`

Why it works:

- information changes route choice
- player does not need `office_pass`
- back-system access is achieved through knowledge of service flow, not formal access

#### Gate 2: “Reach the restricted archive”

This is the critical pseudo OR-gate.

##### Path A: original item path

- move to `storage_room`
- search `desk_safe`
- take `archive_key`
- move `storage_room -> restricted_archive`

Runtime interpretation:

- hard item-gated edge

##### Path B: information-driven path

- learn from `routing_slip`, `assistant_archivist_npc`, or `janitor_npc` that the document lift reaches archive shelving
- move `reading_room -> returns_annex`
- inspect/search `document_lift`
- move `returns_annex -> restricted_archive`

Runtime interpretation:

- no new gate model
- just an alternate authored connection that becomes practically available only after the player learns it is meaningful

Both paths are viable and testable:

- Path A tests item-gated progression
- Path B tests information-shaped routing without mandatory key acquisition

### Information Chain

#### Player learns location

- `porter_npc` points toward the clerk
- `reference_index` confirms the forged file belongs in `restricted_archive`
- `shift_ledger` confirms it was moved after hours

#### Player learns method

- `lost_and_found_tray` gives the office-access method
- `desk_safe` gives the official archive-access method
- `returns_cart` gives the service-bypass method through `routing_slip`

#### Player learns alternative

- `assistant_archivist_npc` tells the player that records travel through returns workflow
- `routing_slip` makes that information concrete and actionable
- `janitor_npc` confirms whether the player should trust the official door route or the lift route

#### Explicit clue-to-action chain

- `notice_board` -> ask about after-hours movement -> talk to `assistant_archivist_npc`
- `assistant_archivist_npc` -> search `returns_cart` -> get `routing_slip` -> go to `returns_annex`
- `lost_and_found_tray` -> get `office_pass` -> enter `clerk_office` -> search `desk_safe` -> get `archive_key`
- `shift_ledger` -> understand file was moved -> commit to final archive push

### Optional Branch

Optional branch: `sealed_crate` and `burn_basin`

- reward:
  - `inspection_note`
  - extra evidence that the forgery may have involved coercion, not just greed
- later effect:
  - `assistant_archivist_npc` becomes more direct and less hesitant
  - `janitor_npc` provides stronger confirmation about the safer route
- why this matters:
  - the optional branch changes later interaction quality, not just lore payload

### Soft Consequence Design

This is prompt/context illusion only.

#### If player loops actions

- repeated searches on exhausted clue sources yield emptier responses
- NPCs become terser and stop repeating the clearest version of hints
- player experience effect:
  - wasted turns feel like loss of momentum
  - the scenario feels less cooperative

#### If player ignores clues

- NPC guidance stays vague longer
- the model should keep multiple possibilities open instead of handing over the cleanest route immediately
- player experience effect:
  - brute-force wandering still works, but feels less efficient and less informed

#### If player delays progression

- milestone pressure can be narrated as dawn approaching, staff getting nervous, and windows for quiet access narrowing
- later hints become shorter and more practical instead of explanatory
- player experience effect:
  - urgency increases without adding a real countdown system

#### How the illusion is created

Use only existing prompt/context signals:

- current inventory items such as `office_pass`, `routing_slip`, `inspection_note`
- scene-local entities and whether searchable sources are already emptied
- milestone progression for soft time pressure
- current area and route already chosen by the player

No real dialogue state is required. The GM response changes because the authoritative context already changed.

## 4. Kernel Mapping

### Information changes path choice

- Supported by: `scene_action talk`, `inspect`, `search`, plus authored map connections
- Why no kernel change is needed:
  - the kernel already exposes NPCs, containers, searchable entities, and movement options
  - information affects player routing, not backend permissions

### Pseudo OR-gate

- Supported by: `move`, `search`, `take`
- Why no kernel change is needed:
  - Path A uses a normal item-gated edge
  - Path B uses a different authored connection to the same destination
  - the OR behavior is design-level, not rule-engine-level

### Soft consequence

- Supported by: existing prompt context from authoritative inventory, scene state, milestone, and area state
- Why no kernel change is needed:
  - no new persistence is required
  - the GM can vary tone, clarity, and urgency based on already-persisted state

### Stronger choices

- Supported by: map structure plus multiple clue sources
- Why no kernel change is needed:
  - the kernel already allows multiple routes and multiple searchable objects
  - the scenario becomes less linear because authored content distributes useful clues across branches

## 5. Experience Comparison

| Aspect | Original | Enhanced |
|--------|----------|----------|
| progression | mostly key -> door | official route or service bypass route |
| decision making | low, because clues mostly confirm the same path | higher, because information changes which route is worth pursuing |
| replayability | limited; mainline looks similar every run | better; office-first and service-first runs feel different |
| player agency | moderate; interaction exists but route logic is narrow | stronger; player chooses whom to trust, what to search, and whether to pursue optional evidence |

## 6. Risk Check

### Runtime/tool risks

- `tool_executor`
  - low risk if Path A remains standard `search -> take -> move`
  - low risk if Path B is just a normal alternate edge, not a fake dynamic unlock
- `map/view`
  - low risk if all new entities stay area-local and item reveals use normal stack projection
- `item flow`
  - low risk if only `office_pass`, `archive_key`, `routing_slip`, and `inspection_note` use standard reveal/take flow

### LLM-behavior risks

- Full prompt context already includes map state, so the model may infer the service route earlier than intended.
- If area naming is too explicit, the alternative path may stop feeling “discovered.”
- Because there is no true dialogue memory layer, NPC attitude shifts must be anchored to inventory, scene depletion, and milestone pressure rather than free-form conversational history.
- If both routes are hinted too aggressively at once, the scenario may feel noisy rather than choice-driven.

### Practical ambiguity to watch

- `returns_annex -> restricted_archive` must be described as meaningful only after a clue, even though it exists structurally.
- `routing_slip` must be written as operational information, not flavor text, or G1 fails.
- NPC hint staging must avoid sounding like the GM is arbitrarily withholding obvious information.

## 7. Minimal Test Suggestions

1. Manual/pytest path A:
   - search `lost_and_found_tray`
   - take `office_pass`
   - enter `clerk_office`
   - search `desk_safe`
   - take `archive_key`
   - move through `storage_room -> restricted_archive`

2. Manual/pytest path B:
   - talk to `assistant_archivist_npc`
   - search `returns_cart`
   - take `routing_slip`
   - move `reading_room -> returns_annex -> restricted_archive`
   - verify success without `archive_key`

3. Deadlock check:
   - verify at least one viable route remains if player ignores `lost_and_found_tray`
   - verify at least one viable route remains if player never enters `clerk_office`

4. Optional-branch check:
   - obtain `inspection_note`
   - confirm later NPC responses become more decisive or specific in the prompted playthrough

5. No-false-lock check:
   - verify the official door still rejects movement without `archive_key`
   - verify the service bypass route does not accidentally require the key
