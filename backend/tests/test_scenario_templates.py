from __future__ import annotations

import pytest

from backend.app.scenario_templates import (
    KEY_GATE_SCENARIO_TEMPLATE_ID,
    get_scenario_template,
    list_scenario_templates,
    normalize_scenario_params,
)


def test_scenario_template_registry_loads_key_gate_scenario() -> None:
    templates = list_scenario_templates()

    assert [template.template_id for template in templates] == [
        KEY_GATE_SCENARIO_TEMPLATE_ID
    ]

    template = get_scenario_template(KEY_GATE_SCENARIO_TEMPLATE_ID)
    assert template.template_version == "v0"
    assert template.default_theme == "watchtower"
    assert template.default_area_count == 6
    assert template.default_layout_type == "branch"
    assert template.default_difficulty == "easy"


def test_normalize_scenario_params_defaults_are_deterministic() -> None:
    first = normalize_scenario_params({})
    second = normalize_scenario_params(
        {"scenario_template": f"  {KEY_GATE_SCENARIO_TEMPLATE_ID}  "}
    )

    assert first == second
    assert first.scenario_template == KEY_GATE_SCENARIO_TEMPLATE_ID
    assert first.theme == "watchtower"
    assert first.area_count == 6
    assert first.layout_type == "branch"
    assert first.difficulty == "easy"


def test_normalize_scenario_params_normalizes_valid_string_inputs() -> None:
    params = normalize_scenario_params(
        {
            "scenario_template": " KEY_GATE_SCENARIO ",
            "theme": "  Old Tower  ",
            "layout_type": " LINEAR ",
            "difficulty": " STANDARD ",
        }
    )

    assert params.scenario_template == KEY_GATE_SCENARIO_TEMPLATE_ID
    assert params.theme == "old tower"
    assert params.layout_type == "linear"
    assert params.difficulty == "standard"


def test_normalize_scenario_params_rejects_unsupported_template() -> None:
    with pytest.raises(ValueError, match="unsupported scenario_template"):
        normalize_scenario_params({"scenario_template": "freeform_world"})


@pytest.mark.parametrize("area_count", [4, 8])
def test_normalize_scenario_params_accepts_area_count_bounds(area_count: int) -> None:
    params = normalize_scenario_params({"area_count": area_count})

    assert params.area_count == area_count


@pytest.mark.parametrize("area_count", [3, 9, True])
def test_normalize_scenario_params_rejects_invalid_area_count(area_count: object) -> None:
    with pytest.raises(ValueError, match="area_count"):
        normalize_scenario_params({"area_count": area_count})


@pytest.mark.parametrize("layout_type", ["linear", "branch", "branched", " LINEAR "])
def test_normalize_scenario_params_accepts_known_layout_types(layout_type: str) -> None:
    params = normalize_scenario_params({"layout_type": layout_type})

    assert params.layout_type in {"linear", "branch"}


def test_normalize_scenario_params_rejects_unknown_layout_type() -> None:
    with pytest.raises(ValueError, match="layout_type"):
        normalize_scenario_params({"layout_type": "grid"})


@pytest.mark.parametrize("difficulty", ["easy", "standard", " STANDARD "])
def test_normalize_scenario_params_accepts_known_difficulties(difficulty: str) -> None:
    params = normalize_scenario_params({"difficulty": difficulty})

    assert params.difficulty in {"easy", "standard"}


def test_normalize_scenario_params_rejects_unknown_difficulty() -> None:
    with pytest.raises(ValueError, match="difficulty"):
        normalize_scenario_params({"difficulty": "hard"})


def test_key_gate_scenario_template_declares_required_structural_roles() -> None:
    template = get_scenario_template(KEY_GATE_SCENARIO_TEMPLATE_ID)

    assert set(template.required_roles) == {
        "start_area",
        "hint_source",
        "clue_area",
        "clue_source",
        "granted_item",
        "gate_area",
        "gate_entity",
        "required_item",
        "target_area",
    }
