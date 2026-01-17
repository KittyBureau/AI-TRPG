from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.app.conflict_detector import detect_conflicts
from backend.app.tool_executor import execute_tool_calls
from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE, DIALOG_TYPES
from backend.domain.map_models import normalize_map
from backend.domain.models import (
    AssistantStructured,
    Campaign,
    CampaignSummary,
    ConflictReport,
    Goal,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
    StateSummary,
    ToolCall,
    TurnLogEntry,
)
from backend.domain.state_utils import (
    ensure_positions_child,
    set_parent_position,
    sync_state_positions,
)
from backend.infra.file_repo import FileRepo
from backend.infra.llm_client import LLMClient


class TurnService:
    def __init__(self, repo: FileRepo) -> None:
        self.repo = repo
        self.llm = LLMClient()

    def create_campaign(
        self,
        world_id: str,
        map_id: str,
        party_character_ids: List[str],
        active_actor_id: str,
    ) -> str:
        campaign_id = self.repo.next_campaign_id()
        starter_map = MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Starting Area",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002", name="Side Room", reachable_area_ids=[]
                ),
            },
            connections=[],
        )
        positions = {character_id: "area_001" for character_id in party_character_ids}
        hp = {character_id: 10 for character_id in party_character_ids}
        character_states = {
            character_id: "alive" for character_id in party_character_ids
        }
        selected = Selected(
            world_id=world_id,
            map_id=map_id,
            party_character_ids=party_character_ids,
            active_actor_id=active_actor_id,
        )
        campaign = Campaign(
            id=campaign_id,
            selected=selected,
            settings_snapshot=SettingsSnapshot(),
            goal=Goal(text="Define the main objective", status="active"),
            milestone=Milestone(current="intro", last_advanced_turn=0),
            map=starter_map,
            positions=positions,
            hp=hp,
            character_states=character_states,
        )
        sync_state_positions(campaign)
        ensure_positions_child(campaign, party_character_ids)
        normalize_map(campaign.map)
        self.repo.create_campaign(campaign)
        return campaign_id

    def list_campaigns(self) -> List[CampaignSummary]:
        return self.repo.list_campaigns()

    def select_actor(self, campaign_id: str, actor_id: str) -> Campaign:
        campaign = self.repo.get_campaign(campaign_id)
        if actor_id not in campaign.selected.party_character_ids:
            raise ValueError("actor_id not in party_character_ids")
        return self.repo.update_active_actor(campaign, actor_id)

    def submit_turn(
        self, campaign_id: str, user_input: str, actor_id: Optional[str] = None
    ) -> Dict[str, object]:
        campaign = self.repo.get_campaign(campaign_id)
        state_updated = _ensure_minimum_state(campaign)
        if state_updated:
            self.repo.save_campaign(campaign)
        active_actor_id = actor_id or campaign.selected.active_actor_id
        if active_actor_id not in campaign.selected.party_character_ids:
            raise ValueError("actor_id not in party_character_ids")
        system_prompt = _build_system_prompt(campaign)
        retry_count = 0
        last_conflicts = []
        debug_append = None
        max_retries = 2

        while True:
            llm_output = self.llm.generate(system_prompt, user_input, debug_append)
            dialog_type, dialog_type_source = _resolve_dialog_type(
                llm_output.get("dialog_type")
            )
            tool_calls = _parse_tool_calls(llm_output.get("tool_calls", []))
            state_before = _snapshot_state(campaign)
            applied_actions, tool_feedback = execute_tool_calls(
                campaign, active_actor_id, tool_calls
            )
            state_after = _state_summary_dict(campaign)
            conflicts = detect_conflicts(
                llm_output.get("assistant_text", ""),
                dialog_type,
                applied_actions,
                tool_feedback,
                state_before,
                state_after,
            )

            if conflicts:
                _restore_state(campaign, state_before)
                last_conflicts = conflicts
                if retry_count < max_retries:
                    retry_count += 1
                    debug_append = _build_debug_append(conflicts, campaign)
                    continue
                conflict_report = ConflictReport(
                    retries=retry_count, conflicts=conflicts
                )
                return _build_failure_response(
                    conflict_report, campaign, active_actor_id, dialog_type
                )

            if applied_actions:
                self.repo.save_campaign(campaign)

            conflict_report = (
                ConflictReport(retries=retry_count, conflicts=last_conflicts)
                if retry_count > 0
                else None
            )
            turn_id = self.repo.next_turn_id(campaign_id)
            timestamp = datetime.now(timezone.utc).isoformat()
            entry = TurnLogEntry(
                turn_id=turn_id,
                timestamp=timestamp,
                user_input=user_input,
                dialog_type=dialog_type,
                dialog_type_source=dialog_type_source,
                settings_revision=campaign.settings_revision,
                assistant_text=llm_output.get("assistant_text", ""),
                assistant_structured=AssistantStructured(tool_calls=tool_calls),
                applied_actions=applied_actions,
                tool_feedback=tool_feedback,
                conflict_report=conflict_report,
                state_summary=StateSummary(active_actor_id=active_actor_id),
            )
            entry.state_summary.positions = dict(campaign.positions)
            entry.state_summary.positions_parent = dict(
                campaign.state.positions_parent
            )
            entry.state_summary.positions_child = dict(
                campaign.state.positions_child
            )
            entry.state_summary.hp = dict(campaign.hp)
            entry.state_summary.character_states = dict(campaign.character_states)
            self.repo.append_turn_log(campaign_id, entry)
            return _build_success_response(entry, tool_calls, applied_actions, tool_feedback)


def _ensure_minimum_state(campaign: Campaign) -> bool:
    updated = False
    if not campaign.map.areas:
        campaign.map = MapData(
            areas={
                "area_001": MapArea(
                    id="area_001",
                    name="Starting Area",
                    reachable_area_ids=["area_002"],
                ),
                "area_002": MapArea(
                    id="area_002", name="Side Room", reachable_area_ids=[]
                ),
            },
            connections=[],
        )
        updated = True
    for character_id in campaign.selected.party_character_ids:
        if character_id not in campaign.positions:
            set_parent_position(campaign, character_id, "area_001")
            updated = True
        if character_id not in campaign.hp:
            campaign.hp[character_id] = 10
            updated = True
        if character_id not in campaign.character_states:
            campaign.character_states[character_id] = "alive"
            updated = True
    sync_state_positions(campaign)
    ensure_positions_child(campaign, campaign.selected.party_character_ids)
    normalize_map(campaign.map)
    return updated


def _parse_tool_calls(raw_calls: object) -> List[ToolCall]:
    if not isinstance(raw_calls, list):
        return []
    parsed: List[ToolCall] = []
    for item in raw_calls:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(ToolCall(**item))
        except Exception:
            continue
    return parsed


def _model_to_dict(model: object) -> Dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    return {}


def _snapshot_state(campaign: Campaign) -> Dict[str, object]:
    if hasattr(campaign.map, "model_copy"):
        map_copy = campaign.map.model_copy(deep=True)
    elif hasattr(campaign.map, "copy"):
        map_copy = campaign.map.copy(deep=True)
    else:
        map_copy = deepcopy(campaign.map)
    return {
        "positions": deepcopy(campaign.positions),
        "state": deepcopy(campaign.state),
        "hp": deepcopy(campaign.hp),
        "character_states": deepcopy(campaign.character_states),
        "map": map_copy,
    }


def _restore_state(campaign: Campaign, snapshot: Dict[str, object]) -> None:
    campaign.positions = snapshot["positions"]
    campaign.state = snapshot["state"]
    campaign.hp = snapshot["hp"]
    campaign.character_states = snapshot["character_states"]
    campaign.map = snapshot["map"]


def _state_summary_dict(campaign: Campaign) -> Dict[str, object]:
    return {
        "positions": dict(campaign.positions),
        "positions_parent": dict(campaign.state.positions_parent),
        "positions_child": dict(campaign.state.positions_child),
        "hp": dict(campaign.hp),
        "character_states": dict(campaign.character_states),
    }


def _build_system_prompt(campaign: Campaign) -> str:
    payload = {
        "dialog_types": DIALOG_TYPES,
        "default_dialog_type": DEFAULT_DIALOG_TYPE,
        "allowlist": campaign.allowlist,
        "selected": _model_to_dict(campaign.selected),
        "settings_snapshot": _model_to_dict(campaign.settings_snapshot),
        "map": _model_to_dict(campaign.map),
        "state": _model_to_dict(campaign.state),
        "positions": campaign.positions,
        "hp": campaign.hp,
        "character_states": campaign.character_states,
        "response_format": {
            "assistant_text": "string narrative",
            "dialog_type": "one of dialog_types",
            "tool_calls": "array of tool calls",
        },
    }
    return (
        "You are the AI GM. Output JSON with keys 'assistant_text', 'dialog_type', and 'tool_calls'. "
        "The world state is authoritative and can change only via tool_calls. "
        "Movement is a state change. If you narrate that an actor moved/entered/arrived/left/changed location, "
        "you MUST include a 'move' tool_call in the same response. "
        "If you do not include a 'move' tool_call, do not narrate any completed movement or location change; "
        "you may describe the current scene or discuss options/intentions. "
        "Priority and fallback for movement intent: If the user expresses intent to move (go/move/enter a place), "
        "you MUST output a 'move' tool_call first. When you output a move or move_options tool_call, "
        "assistant_text must be empty ('') or a single very short plan_note; do not narrate completed movement. "
        "If the target is unclear, do not narrate movement; "
        "call 'move_options' to fetch 1-hop options and state that no movement happened yet. "
        "If tool_calls is empty, assistant_text must not describe any completed movement or location change. "
        "If tool_calls is empty, assistant_text MUST be a non-empty GM response (answer, description, or guidance). "
        "assistant_text may be empty ONLY when you are making a tool call (move or move_options). "
        "For questions like 'Can I move?' or 'Where can I go?', call 'move_options' and list the returned "
        "1-hop options; explicitly state that no movement has happened yet. "
        "Examples (JSON outputs, schema-accurate). "
        "Example 1 (move intent is explicit and IDs are known; assistant_text empty; "
        "actor_id/from_area_id/to_area_id must come from Context.selected.active_actor_id and "
        "Context.positions[...] plus the user's specified target): "
        "{\"assistant_text\":\"\",\"dialog_type\":\"scene_description\","
        "\"tool_calls\":[{\"id\":\"call_move_1\",\"tool\":\"move\",\"args\":"
        "{\"actor_id\":\"pc_001\",\"from_area_id\":\"area_001\",\"to_area_id\":\"area_002\"}}]} "
        "Example 2 (target unclear or user asks where they can go; use move_options; no movement yet; "
        "actor_id should come from Context.selected.active_actor_id): "
        "{\"assistant_text\":\"No movement yet. I will fetch 1-hop options.\","
        "\"dialog_type\":\"scene_description\","
        "\"tool_calls\":[{\"id\":\"call_move_options_1\",\"tool\":\"move_options\",\"args\":"
        "{\"actor_id\":\"pc_001\"}}]} "
        "Example 3 (no tool call required; MUST respond with non-empty assistant_text): "
        "{\"assistant_text\":\"You are currently in area_002. The corridor is quiet. What do you do next?\","
        "\"dialog_type\":\"scene_description\",\"tool_calls\":[]} "
        "Do not modify rules, maps, or character sheets. "
        f"Context: {json.dumps(payload, ensure_ascii=False)}"
    )


def _build_debug_append(conflicts: List[object], campaign: Campaign) -> str:
    payload = {
        "conflicts": [_model_to_dict(conflict) for conflict in conflicts],
        "authoritative_state": _state_summary_dict(campaign),
    }
    return (
        "Your last output conflicted with authoritative state. "
        "Fix narrative/tool_calls to comply. "
        f"Debug: {json.dumps(payload, ensure_ascii=True)}"
    )


def _resolve_dialog_type(value: object) -> tuple[str, str]:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in DIALOG_TYPES:
            return normalized, "model"
    return DEFAULT_DIALOG_TYPE, "fallback"


def _build_success_response(
    entry: TurnLogEntry,
    tool_calls: List[ToolCall],
    applied_actions: List[object],
    tool_feedback: object,
) -> Dict[str, object]:
    if hasattr(entry.state_summary, "model_dump"):
        state_summary = entry.state_summary.model_dump()
    elif hasattr(entry.state_summary, "dict"):
        state_summary = entry.state_summary.dict()
    else:
        state_summary = entry.state_summary
    tool_calls_payload = [_model_to_dict(call) for call in tool_calls]
    applied_actions_payload = [_model_to_dict(action) for action in applied_actions]
    tool_feedback_payload = _model_to_dict(tool_feedback) if tool_feedback else None
    conflict_report_payload = (
        _model_to_dict(entry.conflict_report)
        if entry.conflict_report
        else None
    )
    return {
        "narrative_text": entry.assistant_text,
        "dialog_type": entry.dialog_type,
        "tool_calls": tool_calls_payload,
        "applied_actions": applied_actions_payload,
        "tool_feedback": tool_feedback_payload,
        "conflict_report": conflict_report_payload,
        "state_summary": state_summary,
    }


def _build_failure_response(
    conflict_report: ConflictReport,
    campaign: Campaign,
    active_actor_id: str,
    dialog_type: str,
) -> Dict[str, object]:
    state_summary = StateSummary(active_actor_id=active_actor_id)
    state_summary.positions = dict(campaign.positions)
    state_summary.positions_parent = dict(campaign.state.positions_parent)
    state_summary.positions_child = dict(campaign.state.positions_child)
    state_summary.hp = dict(campaign.hp)
    state_summary.character_states = dict(campaign.character_states)
    return {
        "narrative_text": "",
        "dialog_type": dialog_type,
        "tool_calls": [],
        "applied_actions": [],
        "tool_feedback": None,
        "conflict_report": _model_to_dict(conflict_report),
        "state_summary": _model_to_dict(state_summary),
    }
