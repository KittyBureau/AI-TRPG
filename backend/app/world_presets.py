from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional

from backend.domain.formal_gameplay_model import ValidationIssue, ValidationResult
from backend.domain.models import Entity, EntityLocation, MapArea, MapData, RuntimeItemStack
from backend.domain.world_models import World, WorldGenerator, stable_seed_from_world_id, stable_world_timestamp

TEST_WATCHTOWER_WORLD_ID = "test_watchtower_world"
TEST_WATCHTOWER_START_AREA_ID = "village_gate"
TEST_WATCHTOWER_TARGET_AREA_ID = "watchtower_inside"
TEST_WATCHTOWER_GATE_FROM_AREA_ID = "watchtower_entrance"
TEST_WATCHTOWER_GATE_ITEM_ID = "tower_key"
TEST_WATCHTOWER_GATE_STACK_ID = "stk_watchtower_tower_key_01"
MIDNIGHT_ARCHIVE_WORLD_ID = "midnight_archive_world"
MIDNIGHT_ARCHIVE_START_AREA_ID = "street_gate"
MIDNIGHT_ARCHIVE_TARGET_AREA_ID = "restricted_archive"
MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID = "forged_file_shelf"
MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_FROM_AREA_ID = "lobby"
MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_TO_AREA_ID = "clerk_office"
MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_ITEM_ID = "office_pass"
MIDNIGHT_ARCHIVE_ARCHIVE_GATE_FROM_AREA_ID = "storage_room"
MIDNIGHT_ARCHIVE_ARCHIVE_GATE_ITEM_ID = "archive_key"
MIDNIGHT_ARCHIVE_SERVICE_ROUTE_FROM_AREA_ID = "returns_annex"
MIDNIGHT_ARCHIVE_SERVICE_ROUTE_ITEM_ID = "routing_slip"
MIDNIGHT_ARCHIVE_OFFICE_PASS_STACK_ID = "stk_midnight_office_pass_01"
MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID = "stk_midnight_routing_slip_01"
MIDNIGHT_ARCHIVE_ARCHIVE_KEY_STACK_ID = "stk_midnight_archive_key_01"
MIDNIGHT_ARCHIVE_INSPECTION_NOTE_STACK_ID = "stk_midnight_inspection_note_01"
# Internal development preset for the scenario-generator v0 runtime path.
DEV_KEY_GATE_SCENARIO_WORLD_ID = "dev_key_gate_scenario_world"


@dataclass(frozen=True)
class CampaignWorldPreset:
    start_area_id: str
    goal_text: str
    map_data: MapData
    items: Dict[str, RuntimeItemStack]
    entities: Dict[str, Entity]
    formal_validation: ValidationResult | None = None


def build_world_preset(world_id: str) -> Optional[World]:
    normalized_world_id = world_id.strip()
    if normalized_world_id == DEV_KEY_GATE_SCENARIO_WORLD_ID:
        now = stable_world_timestamp(normalized_world_id)
        return World(
            world_id=normalized_world_id,
            name="Dev Key Gate Scenario World",
            seed=stable_seed_from_world_id(normalized_world_id),
            world_description=(
                "A scenario-backed development preset for validating the key-gate runtime path."
            ),
            objective="Find the required item and enter the target area.",
            start_area="area_start",
            generator=WorldGenerator(
                id="playable_scenario_v0",
                version="1",
                params={
                    "mode": "playable_scenario",
                    "template_id": "key_gate_scenario",
                    "template_version": "v0",
                    "theme": "watchtower",
                    "area_count": 4,
                    "layout_type": "linear",
                    "difficulty": "easy",
                },
            ),
            schema_version="1",
            created_at=now,
            updated_at=now,
        )
    if normalized_world_id == MIDNIGHT_ARCHIVE_WORLD_ID:
        now = stable_world_timestamp(normalized_world_id)
        return World(
            world_id=normalized_world_id,
            name="Midnight Archive",
            seed=stable_seed_from_world_id(normalized_world_id),
            world_description=(
                "A fixed investigation scenario set in a rain-soaked civic archive with an official route and a service-route bypass."
            ),
            objective=(
                "Reach the restricted archive and inspect the forged file shelf to recover proof that the inspection record was falsified."
            ),
            start_area=MIDNIGHT_ARCHIVE_START_AREA_ID,
            generator=WorldGenerator(
                id="static_test_world",
                version="1",
                params={"preset_id": normalized_world_id, "content_mode": "fixed"},
            ),
            schema_version="1",
            created_at=now,
            updated_at=now,
        )
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    now = stable_world_timestamp(normalized_world_id)
    return World(
        world_id=normalized_world_id,
        name="Test Watchtower World",
        seed=stable_seed_from_world_id(normalized_world_id),
        world_description=(
            "A fixed smoke-test world with a village approach, an old hut, and a locked watchtower."
        ),
        objective="Find the tower key in the old hut and enter the watchtower.",
        start_area=TEST_WATCHTOWER_START_AREA_ID,
        generator=WorldGenerator(
            id="static_test_world",
            version="1",
            params={"preset_id": normalized_world_id, "content_mode": "fixed"},
        ),
        schema_version="1",
        created_at=now,
        updated_at=now,
    )


def list_world_presets() -> list[World]:
    preset_ids = [
        DEV_KEY_GATE_SCENARIO_WORLD_ID,
        MIDNIGHT_ARCHIVE_WORLD_ID,
        TEST_WATCHTOWER_WORLD_ID,
    ]
    return [
        preset
        for preset in (build_world_preset(preset_id) for preset_id in preset_ids)
        if preset is not None
    ]


def build_campaign_world_preset(world_id: str) -> Optional[CampaignWorldPreset]:
    normalized_world_id = world_id.strip()
    if normalized_world_id == MIDNIGHT_ARCHIVE_WORLD_ID:
        preset = CampaignWorldPreset(
            start_area_id=MIDNIGHT_ARCHIVE_START_AREA_ID,
            goal_text=(
                "Reach the restricted archive and inspect the forged file shelf to recover proof that the inspection record was falsified."
            ),
            map_data=MapData(
                areas={
                    "street_gate": MapArea(
                        id="street_gate",
                        name="Street Gate",
                        description="Rain drums on the archive steps while a tired porter guards the entrance.",
                        reachable_area_ids=["lobby"],
                    ),
                    "lobby": MapArea(
                        id="lobby",
                        name="Lobby",
                        description="A wet stone lobby with notices, a tray, and the clerk's locked office door.",
                        reachable_area_ids=["street_gate", "reading_room", "clerk_office"],
                    ),
                    "reading_room": MapArea(
                        id="reading_room",
                        name="Reading Room",
                        description="Catalog drawers and late returns sit under weak green lamps.",
                        reachable_area_ids=["lobby", "returns_annex"],
                    ),
                    "returns_annex": MapArea(
                        id="returns_annex",
                        name="Returns Annex",
                        description="A service annex where after-hours document traffic feeds toward the archive stacks.",
                        reachable_area_ids=["reading_room", "storage_room", "restricted_archive"],
                    ),
                    "clerk_office": MapArea(
                        id="clerk_office",
                        name="Clerk Office",
                        description="A cramped office with a safe, a ledger, and a basin of burned paper.",
                        reachable_area_ids=["lobby", "storage_room"],
                    ),
                    "storage_room": MapArea(
                        id="storage_room",
                        name="Storage Room",
                        description="Dusty shelving, a night janitor, and the official archive door.",
                        reachable_area_ids=["clerk_office", "returns_annex", "restricted_archive"],
                    ),
                    "restricted_archive": MapArea(
                        id="restricted_archive",
                        name="Restricted Archive",
                        description="Cold shelves and sealed drawers hold the hidden inspection file.",
                        reachable_area_ids=["storage_room", "returns_annex"],
                    ),
                },
                connections=[],
            ),
            items={},
            entities={
                "porter_npc": Entity(
                    id="porter_npc",
                    kind="npc",
                    label="Night Porter",
                    tags=["npc", "porter", "hint"],
                    loc=EntityLocation(type="area", id="street_gate"),
                    verbs=["inspect", "talk"],
                    state={
                        "hint": (
                            "The duty clerk has been guarding his office all night. "
                            "If records moved after hours, the reading room or returns annex will know it."
                        )
                    },
                    props={},
                ),
                "notice_board": Entity(
                    id="notice_board",
                    kind="object",
                    label="Notice Board",
                    tags=["notice", "workflow"],
                    loc=EntityLocation(type="area", id="lobby"),
                    verbs=["inspect"],
                    state={
                        "hint": "A posted workflow mentions returns intake before restricted shelving transfer."
                    },
                    props={},
                ),
                "lost_and_found_tray": Entity(
                    id="lost_and_found_tray",
                    kind="container",
                    label="Lost-and-Found Tray",
                    tags=["tray", "search_spot"],
                    loc=EntityLocation(type="area", id="lobby"),
                    verbs=["inspect", "search"],
                    state={
                        "opened": True,
                        "hint": "Someone dropped a clerk-access pass here in a hurry.",
                        "search_loot_stack_id": MIDNIGHT_ARCHIVE_OFFICE_PASS_STACK_ID,
                        "search_loot_definition_id": MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_ITEM_ID,
                        "search_loot_label": "Office Pass",
                        "search_loot_tags": ["pass"],
                        "search_loot_stackable": False,
                    },
                    props={},
                ),
                "duty_roster": Entity(
                    id="duty_roster",
                    kind="object",
                    label="Duty Roster",
                    tags=["record", "staff"],
                    loc=EntityLocation(type="area", id="lobby"),
                    verbs=["inspect"],
                    state={
                        "hint": "The assistant archivist and janitor were both on the late shift."
                    },
                    props={},
                ),
                "assistant_archivist_npc": Entity(
                    id="assistant_archivist_npc",
                    kind="npc",
                    label="Assistant Archivist",
                    tags=["npc", "archivist", "hint"],
                    loc=EntityLocation(type="area", id="reading_room"),
                    verbs=["inspect", "talk"],
                    state={
                        "hint": (
                            "Official cabinets are locked, but records do not always travel by official means. "
                            "Check the returns workflow if you need another route."
                        )
                    },
                    props={},
                ),
                "returns_cart": Entity(
                    id="returns_cart",
                    kind="container",
                    label="Returns Cart",
                    tags=["cart", "search_spot", "route_clue"],
                    loc=EntityLocation(type="area", id="reading_room"),
                    verbs=["inspect", "search"],
                    state={
                        "opened": True,
                        "hint": "A routing slip links late returns processing to the service lift.",
                        "search_loot_stack_id": MIDNIGHT_ARCHIVE_ROUTING_SLIP_STACK_ID,
                        "search_loot_definition_id": "routing_slip",
                        "search_loot_label": "Routing Slip",
                        "search_loot_tags": ["paperwork", "route"],
                        "search_loot_stackable": False,
                    },
                    props={},
                ),
                "reference_index": Entity(
                    id="reference_index",
                    kind="object",
                    label="Reference Index",
                    tags=["catalog", "record"],
                    loc=EntityLocation(type="area", id="reading_room"),
                    verbs=["inspect"],
                    state={
                        "hint": "The missing inspection file belongs in the restricted archive stacks."
                    },
                    props={},
                ),
                "document_lift": Entity(
                    id="document_lift",
                    kind="object",
                    label="Document Lift",
                    tags=["lift", "service_route"],
                    loc=EntityLocation(type="area", id="returns_annex"),
                    verbs=["inspect"],
                    state={
                        "hint": "The service lift runs directly beside the restricted archive shelving."
                    },
                    props={},
                ),
                "sealed_crate": Entity(
                    id="sealed_crate",
                    kind="object",
                    label="Sealed Crate",
                    tags=["crate", "optional"],
                    loc=EntityLocation(type="area", id="returns_annex"),
                    verbs=["inspect"],
                    state={
                        "hint": "Most of this is harmless intake, but one note references an inspection rewrite."
                    },
                    props={},
                ),
                "desk_safe": Entity(
                    id="desk_safe",
                    kind="container",
                    label="Desk Safe",
                    tags=["safe", "search_spot"],
                    loc=EntityLocation(type="area", id="clerk_office"),
                    verbs=["inspect", "open", "search"],
                    state={
                        "opened": False,
                        "locked": False,
                        "hint": "If the clerk hid the file, the archive key is probably close by.",
                        "search_loot_stack_id": MIDNIGHT_ARCHIVE_ARCHIVE_KEY_STACK_ID,
                        "search_loot_definition_id": MIDNIGHT_ARCHIVE_ARCHIVE_GATE_ITEM_ID,
                        "search_loot_label": "Archive Key",
                        "search_loot_tags": ["key"],
                        "search_loot_stackable": False,
                    },
                    props={},
                ),
                "shift_ledger": Entity(
                    id="shift_ledger",
                    kind="object",
                    label="Shift Ledger",
                    tags=["ledger", "record"],
                    loc=EntityLocation(type="area", id="clerk_office"),
                    verbs=["inspect"],
                    state={
                        "hint": "A late entry shows restricted files moved after the public floor closed."
                    },
                    props={},
                ),
                "burn_basin": Entity(
                    id="burn_basin",
                    kind="container",
                    label="Burn Basin",
                    tags=["evidence", "optional"],
                    loc=EntityLocation(type="area", id="clerk_office"),
                    verbs=["inspect", "search"],
                    state={
                        "opened": True,
                        "hint": "Half-burned scraps suggest someone rewrote the record in panic.",
                        "search_loot_stack_id": MIDNIGHT_ARCHIVE_INSPECTION_NOTE_STACK_ID,
                        "search_loot_definition_id": "inspection_note",
                        "search_loot_label": "Inspection Note",
                        "search_loot_tags": ["note", "evidence"],
                        "search_loot_stackable": False,
                    },
                    props={},
                ),
                "janitor_npc": Entity(
                    id="janitor_npc",
                    kind="npc",
                    label="Night Janitor",
                    tags=["npc", "janitor", "hint"],
                    loc=EntityLocation(type="area", id="storage_room"),
                    verbs=["inspect", "talk"],
                    state={
                        "hint": "That archive door wants a key. The lift route is quieter if you know how records move."
                    },
                    props={},
                ),
                "archive_door": Entity(
                    id="archive_door",
                    kind="object",
                    label="Archive Door",
                    tags=["door", "gate", "locked"],
                    loc=EntityLocation(type="area", id="storage_room"),
                    verbs=["inspect", "open"],
                    state={"locked": True},
                    props={},
                ),
                "forged_file_shelf": Entity(
                    id=MIDNIGHT_ARCHIVE_PAYOFF_ENTITY_ID,
                    kind="object",
                    label="Forged File Shelf",
                    tags=["goal", "archive"],
                    loc=EntityLocation(type="area", id="restricted_archive"),
                    verbs=["inspect", "search"],
                    state={
                        "hint": (
                            "The hidden inspection record is here. Inspect or search the shelf to confirm the forgery and finish the scenario."
                        )
                    },
                    props={},
                ),
            },
        )
        return _attach_preset_formal_validation(normalized_world_id, preset)
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    preset = CampaignWorldPreset(
        start_area_id=TEST_WATCHTOWER_START_AREA_ID,
        goal_text="Find the tower key in the old hut and enter the watchtower.",
        map_data=MapData(
            areas={
                "village_gate": MapArea(
                    id="village_gate",
                    name="Village Gate",
                    description="A weathered gate faces the abandoned watchtower road.",
                    reachable_area_ids=["village_square"],
                ),
                "village_square": MapArea(
                    id="village_square",
                    name="Village Square",
                    description="An empty square where the hut path and forest path split.",
                    reachable_area_ids=["village_gate", "old_hut", "forest_path"],
                ),
                "old_hut": MapArea(
                    id="old_hut",
                    name="Old Hut",
                    description="A dusty hut with a loose floorboard and signs of hurried departure.",
                    reachable_area_ids=["village_square"],
                ),
                "forest_path": MapArea(
                    id="forest_path",
                    name="Forest Path",
                    description="A narrow path climbs toward the sealed watchtower entrance.",
                    reachable_area_ids=["village_square", "watchtower_entrance"],
                ),
                "watchtower_entrance": MapArea(
                    id="watchtower_entrance",
                    name="Watchtower Entrance",
                    description="A heavy wooden tower door blocks the way inside.",
                    reachable_area_ids=["forest_path", "watchtower_inside"],
                ),
                "watchtower_inside": MapArea(
                    id="watchtower_inside",
                    name="Watchtower Interior",
                    description="The silent watch room confirms the objective is complete.",
                    reachable_area_ids=["watchtower_entrance"],
                ),
            },
            connections=[],
        ),
        items={},
        entities={
            "npc_village_guard": Entity(
                id="npc_village_guard",
                kind="npc",
                label="Village Guard",
                tags=["npc", "guard", "hint"],
                loc=EntityLocation(type="area", id="village_gate"),
                verbs=["inspect", "talk"],
                state={
                    "hint": "The watchtower key was left in the old hut near the square."
                },
                props={},
            ),
            "old_hut_clue": Entity(
                id="old_hut_clue",
                kind="container",
                label="Loose Floorboard",
                tags=["clue", "search_spot", "stash"],
                loc=EntityLocation(type="area", id="old_hut"),
                verbs=["inspect", "search"],
                state={
                    "hint": "Something small was hidden here: the tower key.",
                    "opened": True,
                    "search_loot_stack_id": TEST_WATCHTOWER_GATE_STACK_ID,
                    "search_loot_definition_id": TEST_WATCHTOWER_GATE_ITEM_ID,
                    "search_loot_label": "Tower Key",
                    "search_loot_tags": ["key"],
                    "search_loot_stackable": False,
                },
                props={},
            ),
            "watchtower_door": Entity(
                id="watchtower_door",
                kind="object",
                label="Watchtower Door",
                tags=["door", "gate", "locked"],
                loc=EntityLocation(type="area", id="watchtower_entrance"),
                verbs=["inspect", "open"],
                state={
                    "locked": True,
                },
                props={},
            ),
        },
    )
    return _attach_preset_formal_validation(normalized_world_id, preset)


def required_item_for_move(
    world_id: str,
    from_area_id: str,
    to_area_id: str,
) -> Optional[str]:
    normalized_world_id = world_id.strip()
    if normalized_world_id == MIDNIGHT_ARCHIVE_WORLD_ID:
        if (
            from_area_id == MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_FROM_AREA_ID
            and to_area_id == MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_TO_AREA_ID
        ):
            return MIDNIGHT_ARCHIVE_OFFICIAL_ROUTE_ITEM_ID
        if (
            from_area_id == MIDNIGHT_ARCHIVE_ARCHIVE_GATE_FROM_AREA_ID
            and to_area_id == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
        ):
            return MIDNIGHT_ARCHIVE_ARCHIVE_GATE_ITEM_ID
        if (
            from_area_id == MIDNIGHT_ARCHIVE_SERVICE_ROUTE_FROM_AREA_ID
            and to_area_id == MIDNIGHT_ARCHIVE_TARGET_AREA_ID
        ):
            return MIDNIGHT_ARCHIVE_SERVICE_ROUTE_ITEM_ID
        return None
    if normalized_world_id != TEST_WATCHTOWER_WORLD_ID:
        return None
    if (
        from_area_id == TEST_WATCHTOWER_GATE_FROM_AREA_ID
        and to_area_id == TEST_WATCHTOWER_TARGET_AREA_ID
    ):
        return TEST_WATCHTOWER_GATE_ITEM_ID
    return None


def is_goal_area(world_id: str, area_id: str) -> bool:
    normalized_world_id = world_id.strip()
    return normalized_world_id == TEST_WATCHTOWER_WORLD_ID and area_id == TEST_WATCHTOWER_TARGET_AREA_ID


def _attach_preset_formal_validation(
    world_id: str,
    preset: CampaignWorldPreset,
) -> CampaignWorldPreset:
    try:
        from backend.app.formal_preset_mapper import build_formal_model_from_preset
        from backend.app.formal_validator import validate_formal_model

        formal_model = build_formal_model_from_preset(world_id, preset)
        if formal_model is None:
            return preset
        validation = validate_formal_model(formal_model)
    except Exception as exc:
        validation = ValidationResult(
            main_path_solvable=False,
            issues=[
                ValidationIssue(
                    code="missing_structure",
                    refs={
                        "kind": "preset_formal_mapping",
                        "world_id": world_id,
                        "reason": str(exc),
                    },
                )
            ],
        )
    return replace(preset, formal_validation=validation)
