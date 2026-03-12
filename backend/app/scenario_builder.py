from __future__ import annotations

from typing import Dict, List, Tuple

from backend.app.scenario_templates import (
    KEY_GATE_SCENARIO_TEMPLATE_ID,
    get_scenario_template,
)
from backend.domain.scenario_models import (
    MaterializedScenario,
    ScenarioArea,
    ScenarioEntity,
    ScenarioGateRule,
    ScenarioGoalRule,
    ScenarioItem,
    ScenarioParams,
    ScenarioRoleAssignments,
    ScenarioTemplateDefinition,
    ScenarioTopology,
)

_START_AREA_ID = "area_start"
_CLUE_AREA_ID = "area_clue"
_GATE_AREA_ID = "area_gate"
_TARGET_AREA_ID = "area_target"
_HINT_SOURCE_ID = "hint_source_001"
_CLUE_SOURCE_ID = "clue_source_001"
_GATE_ENTITY_ID = "gate_001"
_REQUIRED_ITEM_ID = "required_item_001"


def build_materialized_scenario(params: ScenarioParams) -> MaterializedScenario:
    template = get_scenario_template(params.scenario_template)
    return build_materialized_scenario_from_template(params, template)


def build_materialized_scenario_from_template(
    params: ScenarioParams,
    template: ScenarioTemplateDefinition,
) -> MaterializedScenario:
    if template.template_id != KEY_GATE_SCENARIO_TEMPLATE_ID:
        raise ValueError(f"unsupported template for Phase 2: {template.template_id}")
    if params.scenario_template != template.template_id:
        raise ValueError("params.scenario_template does not match template.template_id")

    mainline_transits, branch_transits = _build_transit_plan(params)
    main_path_area_ids = _build_main_path_area_ids(mainline_transits)
    branch_area_ids = _build_branch_area_ids(branch_transits)
    areas = _build_areas(main_path_area_ids, branch_area_ids, params)

    roles = ScenarioRoleAssignments(
        start_area_id=_START_AREA_ID,
        hint_source_id=_HINT_SOURCE_ID,
        clue_area_id=_CLUE_AREA_ID,
        clue_source_id=_CLUE_SOURCE_ID,
        granted_item_id=_REQUIRED_ITEM_ID,
        gate_area_id=_GATE_AREA_ID,
        gate_entity_id=_GATE_ENTITY_ID,
        required_item_id=_REQUIRED_ITEM_ID,
        target_area_id=_TARGET_AREA_ID,
    )

    entities = {
        _HINT_SOURCE_ID: ScenarioEntity(
            id=_HINT_SOURCE_ID,
            kind="hint_source",
            area_id=roles.start_area_id,
        ),
        _CLUE_SOURCE_ID: ScenarioEntity(
            id=_CLUE_SOURCE_ID,
            kind="clue_source",
            area_id=roles.clue_area_id,
            grants_item_id=roles.granted_item_id,
        ),
        _GATE_ENTITY_ID: ScenarioEntity(
            id=_GATE_ENTITY_ID,
            kind="gate",
            area_id=roles.gate_area_id,
            requires_item_id=roles.required_item_id,
        ),
    }
    items = {
        _REQUIRED_ITEM_ID: ScenarioItem(
            id=_REQUIRED_ITEM_ID,
            granted_by_entity_id=roles.clue_source_id,
            required_by_gate_entity_id=roles.gate_entity_id,
        )
    }

    return MaterializedScenario(
        template_id=template.template_id,
        template_version=template.template_version,
        params=params,
        roles=roles,
        topology=ScenarioTopology(
            area_ids_in_order=tuple(main_path_area_ids + branch_area_ids),
            main_path_area_ids=tuple(main_path_area_ids),
            branch_area_ids=tuple(branch_area_ids),
            areas=areas,
        ),
        entities=entities,
        items=items,
        gate_rule=ScenarioGateRule(
            from_area_id=roles.gate_area_id,
            to_area_id=roles.target_area_id,
            required_item_id=roles.required_item_id,
            gate_entity_id=roles.gate_entity_id,
        ),
        goal_rule=ScenarioGoalRule(
            type="enter_area",
            target_area_id=roles.target_area_id,
        ),
    )


def _build_transit_plan(params: ScenarioParams) -> tuple[list[str], list[str]]:
    extra_areas = params.area_count - 4
    if extra_areas < 0:
        raise ValueError("area_count is below the required structural minimum")

    branch_count = 1 if params.layout_type == "branch" and extra_areas > 0 else 0
    mainline_extra_count = extra_areas - branch_count
    before_clue_count, before_gate_count = _split_mainline_transits(
        mainline_extra_count,
        difficulty=params.difficulty,
    )

    transit_ids: List[str] = []
    transit_ids.extend(
        f"area_transit_pre_clue_{index:02d}" for index in range(1, before_clue_count + 1)
    )
    transit_ids.extend(
        f"area_transit_pre_gate_{index:02d}" for index in range(1, before_gate_count + 1)
    )
    branch_ids = [
        f"area_transit_branch_{index:02d}" for index in range(1, branch_count + 1)
    ]
    return transit_ids, branch_ids


def _split_mainline_transits(
    count: int,
    *,
    difficulty: str,
) -> tuple[int, int]:
    if count <= 0:
        return 0, 0
    if difficulty == "easy":
        before_clue = count // 3
    else:
        before_clue = (count + 1) // 2
    if before_clue < 0:
        before_clue = 0
    if before_clue > count:
        before_clue = count
    before_gate = count - before_clue
    return before_clue, before_gate


def _build_main_path_area_ids(mainline_transits: list[str]) -> list[str]:
    pre_clue = [item for item in mainline_transits if "pre_clue" in item]
    pre_gate = [item for item in mainline_transits if "pre_gate" in item]
    return [
        _START_AREA_ID,
        *pre_clue,
        _CLUE_AREA_ID,
        *pre_gate,
        _GATE_AREA_ID,
        _TARGET_AREA_ID,
    ]


def _build_branch_area_ids(branch_transits: list[str]) -> list[str]:
    return list(branch_transits)


def _build_areas(
    main_path_area_ids: list[str],
    branch_area_ids: list[str],
    params: ScenarioParams,
) -> Dict[str, ScenarioArea]:
    adjacency: Dict[str, List[str]] = {area_id: [] for area_id in main_path_area_ids}
    for area_id in branch_area_ids:
        adjacency[area_id] = []

    for index in range(len(main_path_area_ids) - 1):
        _connect(adjacency, main_path_area_ids[index], main_path_area_ids[index + 1])

    if branch_area_ids:
        branch_anchor_id = _START_AREA_ID
        _connect(adjacency, branch_anchor_id, branch_area_ids[0])
        for index in range(len(branch_area_ids) - 1):
            _connect(adjacency, branch_area_ids[index], branch_area_ids[index + 1])

    areas: Dict[str, ScenarioArea] = {}
    main_path_set = set(main_path_area_ids)
    for area_id, connected_area_ids in adjacency.items():
        areas[area_id] = ScenarioArea(
            id=area_id,
            kind=_resolve_area_kind(
                area_id,
                main_path_set=main_path_set,
                branch_area_ids=branch_area_ids,
                params=params,
            ),
            connected_area_ids=tuple(sorted(connected_area_ids)),
        )
    return areas


def _connect(adjacency: Dict[str, List[str]], left: str, right: str) -> None:
    if right not in adjacency[left]:
        adjacency[left].append(right)
    if left not in adjacency[right]:
        adjacency[right].append(left)


def _resolve_area_kind(
    area_id: str,
    *,
    main_path_set: set[str],
    branch_area_ids: list[str],
    params: ScenarioParams,
) -> str:
    if area_id == _START_AREA_ID:
        return "start"
    if area_id == _CLUE_AREA_ID:
        return "clue"
    if area_id == _GATE_AREA_ID:
        return "gate"
    if area_id == _TARGET_AREA_ID:
        return "target"
    if area_id in branch_area_ids or area_id in main_path_set:
        return "transit"
    raise ValueError(f"unclassified area id during build: {area_id} ({params.layout_type})")
