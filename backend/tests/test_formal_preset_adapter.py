from __future__ import annotations

from backend.app.formal_preset_mapper import build_formal_model_from_preset
from backend.app.formal_validator import validate_formal_model
from backend.app.turn_service import TurnService
from backend.app.world_presets import (
    MIDNIGHT_ARCHIVE_WORLD_ID,
    TEST_WATCHTOWER_WORLD_ID,
    build_campaign_world_preset,
)
from backend.infra.file_repo import FileRepo


def test_watchtower_preset_formal_mapping_builds_expected_structure() -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(TEST_WATCHTOWER_WORLD_ID, preset)

    assert model is not None
    node_types = {node.id: node.type for node in model.nodes}
    assert node_types["watchtower_door"] == "gate"
    assert node_types["old_hut_clue"] == "clue_source"
    assert node_types["tower_key"] == "item_dependency"
    assert all(node.type != "goal" for node in model.nodes)
    assert model.goals[0].type == "enter_area"
    assert model.goals[0].target_id == "watchtower_inside"


def test_watchtower_preset_validation_is_solvable() -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(TEST_WATCHTOWER_WORLD_ID, preset)
    assert model is not None
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.issues == []


def test_midnight_archive_preset_formal_mapping_builds_expected_structure() -> None:
    preset = build_campaign_world_preset(MIDNIGHT_ARCHIVE_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(MIDNIGHT_ARCHIVE_WORLD_ID, preset)

    assert model is not None
    node_types = {node.id: node.type for node in model.nodes}
    assert node_types["returns_cart"] == "clue_source"
    assert node_types["routing_slip"] == "item_dependency"
    assert node_types["midnight_archive_service_gate"] == "gate"
    assert node_types["forged_file_shelf"] == "goal"
    assert model.goals[0].type == "interact_entity"
    assert model.goals[0].target_id == "forged_file_shelf"


def test_midnight_archive_preset_validation_is_solvable() -> None:
    preset = build_campaign_world_preset(MIDNIGHT_ARCHIVE_WORLD_ID)
    assert preset is not None

    model = build_formal_model_from_preset(MIDNIGHT_ARCHIVE_WORLD_ID, preset)
    assert model is not None
    result = validate_formal_model(model)

    assert result.main_path_solvable is True
    assert result.issues == []


def test_preset_formal_validation_attaches_without_changing_bootstrap_behavior(
    tmp_path,
) -> None:
    preset = build_campaign_world_preset(TEST_WATCHTOWER_WORLD_ID)
    assert preset is not None
    assert preset.formal_validation is not None
    assert preset.formal_validation.main_path_solvable is True

    repo = FileRepo(tmp_path / "storage")
    service = TurnService(repo)
    campaign_id = service.create_campaign(
        world_id=TEST_WATCHTOWER_WORLD_ID,
        map_id="map_watchtower",
        party_character_ids=["pc_001"],
        active_actor_id="pc_001",
    )

    campaign = repo.get_campaign(campaign_id)
    assert campaign.actors["pc_001"].position == preset.start_area_id
    assert campaign.goal.text == preset.goal_text
