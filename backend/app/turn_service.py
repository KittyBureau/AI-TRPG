from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.app.character_facade_factory import create_runtime_character_facade
from backend.app.conflict_detector import detect_conflicts
from backend.app.tool_executor import execute_tool_calls
from backend.domain.character_access import (
    CharacterState,
)
from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE, DIALOG_TYPES
from backend.domain.map_models import normalize_map
from backend.domain.models import (
    AssistantStructured,
    Campaign,
    CampaignSummary,
    ConflictReport,
    Goal,
    FailedCall,
    ActorState,
    MapArea,
    MapData,
    Milestone,
    Selected,
    SettingsSnapshot,
    StateSummary,
    ToolCall,
    ToolFeedback,
    TurnLogEntry,
)
from backend.domain.state_utils import (
    DEFAULT_CHARACTER_STATE,
    DEFAULT_HP,
)
from backend.infra.file_repo import FileRepo
from backend.infra.llm_client import LLMClient

_CHARACTER_FACADE = create_runtime_character_facade()


class SemanticGuardError(ValueError):
    pass


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
        actors = {
            character_id: ActorState(
                position="area_001",
                hp=DEFAULT_HP,
                character_state=DEFAULT_CHARACTER_STATE,
                meta={},
            )
            for character_id in party_character_ids
        }
        if active_actor_id not in actors:
            actors[active_actor_id] = ActorState(
                position="area_001",
                hp=DEFAULT_HP,
                character_state=DEFAULT_CHARACTER_STATE,
                meta={},
            )
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
            actors=actors,
        )
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
        if _mark_ended_if_needed(campaign):
            self.repo.save_campaign(campaign)
        _assert_turn_writable(campaign, active_actor_id)
        system_prompt = _build_system_prompt(campaign, active_actor_id)
        retry_count = 0
        last_conflicts = []
        debug_append = None
        max_retries = 2

        while True:
            llm_output = self.llm.generate(system_prompt, user_input, debug_append)
            raw_dialog_type = llm_output.get("dialog_type")
            _enforce_dialog_type_guard(
                raw_dialog_type,
                strict_mode=campaign.settings_snapshot.dialog.strict_semantic_guard,
            )
            dialog_type, dialog_type_source = _resolve_dialog_type(raw_dialog_type)
            tool_calls = _parse_tool_calls(llm_output.get("tool_calls", []))
            tool_calls, suppressed_failed_calls = _suppress_repeated_illegal_requests(
                self.repo,
                campaign_id,
                tool_calls,
            )
            state_before = _snapshot_state(campaign)
            applied_actions, tool_feedback = execute_tool_calls(
                campaign, active_actor_id, tool_calls
            )
            if suppressed_failed_calls:
                failed_calls = list(suppressed_failed_calls)
                if tool_feedback:
                    failed_calls.extend(tool_feedback.failed_calls)
                tool_feedback = ToolFeedback(failed_calls=failed_calls)
            state_after = _state_summary_dict(campaign)
            conflicts = detect_conflicts(
                llm_output.get("assistant_text", ""),
                dialog_type,
                applied_actions,
                tool_feedback,
                state_before,
                state_after,
                enable_text_checks=(
                    campaign.settings_snapshot.dialog.conflict_text_checks_enabled
                ),
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

            turn_id = self.repo.next_turn_id(campaign_id)
            turn_number = _turn_id_to_number(turn_id)
            milestone_changed = _advance_milestone(
                campaign,
                turn_number=turn_number,
                retry_count=retry_count,
            )
            lifecycle_changed = _mark_ended_if_needed(campaign)

            if applied_actions or milestone_changed or lifecycle_changed:
                self.repo.save_campaign(campaign)

            conflict_report = (
                ConflictReport(retries=retry_count, conflicts=last_conflicts)
                if retry_count > 0
                else None
            )
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
            (
                positions,
                positions_parent,
                positions_child,
                hp,
                character_states,
            ) = _derive_character_state_maps(campaign)
            entry.state_summary.positions = positions
            entry.state_summary.positions_parent = positions_parent
            entry.state_summary.positions_child = positions_child
            entry.state_summary.hp = hp
            entry.state_summary.character_states = character_states
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
        state = _CHARACTER_FACADE.get_state(campaign, character_id)
        if state.position is None:
            _CHARACTER_FACADE.set_state(
                campaign,
                character_id,
                CharacterState(
                    position="area_001",
                    hp=state.hp,
                    character_state=state.character_state,
                ),
            )
            updated = True
    if campaign.selected.active_actor_id not in campaign.actors:
        active_actor_id = campaign.selected.active_actor_id
        _CHARACTER_FACADE.get_state(campaign, active_actor_id)
        _CHARACTER_FACADE.set_state(
            campaign,
            active_actor_id,
            CharacterState(
                position=None,
                hp=DEFAULT_HP,
                character_state=DEFAULT_CHARACTER_STATE,
            ),
        )
        updated = True
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
    (
        positions,
        positions_parent,
        positions_child,
        hp,
        character_states,
    ) = _derive_character_state_maps(campaign)
    return {
        "actors": deepcopy(campaign.actors),
        "state": deepcopy(campaign.state),
        "campaign_positions": deepcopy(campaign.positions),
        "campaign_hp": deepcopy(campaign.hp),
        "campaign_character_states": deepcopy(campaign.character_states),
        "positions": positions,
        "positions_parent": positions_parent,
        "positions_child": positions_child,
        "hp": hp,
        "character_states": character_states,
        "map": map_copy,
    }


def _restore_state(campaign: Campaign, snapshot: Dict[str, object]) -> None:
    campaign.actors = snapshot["actors"]
    campaign.state = snapshot["state"]
    campaign.positions = snapshot["campaign_positions"]
    campaign.hp = snapshot["campaign_hp"]
    campaign.character_states = snapshot["campaign_character_states"]
    campaign.map = snapshot["map"]


def _state_summary_dict(campaign: Campaign) -> Dict[str, object]:
    (
        positions,
        positions_parent,
        positions_child,
        hp,
        character_states,
    ) = _derive_character_state_maps(campaign)
    return {
        "positions": positions,
        "positions_parent": positions_parent,
        "positions_child": positions_child,
        "hp": hp,
        "character_states": character_states,
    }


def _derive_character_state_maps(campaign: Campaign) -> tuple[
    Dict[str, str],
    Dict[str, str],
    Dict[str, Optional[str]],
    Dict[str, int],
    Dict[str, str],
]:
    return _CHARACTER_FACADE.build_state_maps(campaign)


def _build_system_prompt(campaign: Campaign, active_actor_id: str) -> str:
    positions, _, _, hp, character_states = _derive_character_state_maps(campaign)
    actors_payload = {
        actor_id: _model_to_dict(actor)
        for actor_id, actor in campaign.actors.items()
    }
    compress_enabled = campaign.settings_snapshot.context.compress_enabled
    if compress_enabled:
        active_state = _CHARACTER_FACADE.get_state(campaign, active_actor_id)
        payload = {
            "context_mode": "compressed",
            "dialog_types": DIALOG_TYPES,
            "default_dialog_type": DEFAULT_DIALOG_TYPE,
            "allowlist": campaign.allowlist,
            "selected": _model_to_dict(campaign.selected),
            "settings_snapshot": _model_to_dict(campaign.settings_snapshot),
            "lifecycle": _model_to_dict(campaign.lifecycle),
            "milestone": _model_to_dict(campaign.milestone),
            "map_summary": {
                "area_count": len(campaign.map.areas),
                "active_actor_area_id": active_state.position,
                "reachable_from_active": (
                    campaign.map.areas[active_state.position].reachable_area_ids
                    if isinstance(active_state.position, str)
                    and active_state.position in campaign.map.areas
                    else []
                ),
            },
            "positions": positions,
            "hp": hp,
            "character_states": character_states,
            "response_format": {
                "assistant_text": "string narrative",
                "dialog_type": "one of dialog_types",
                "tool_calls": "array of tool calls",
            },
        }
    else:
        payload = {
            "context_mode": "full",
            "dialog_types": DIALOG_TYPES,
            "default_dialog_type": DEFAULT_DIALOG_TYPE,
            "allowlist": campaign.allowlist,
            "selected": _model_to_dict(campaign.selected),
            "settings_snapshot": _model_to_dict(campaign.settings_snapshot),
            "lifecycle": _model_to_dict(campaign.lifecycle),
            "milestone": _model_to_dict(campaign.milestone),
            "map": _model_to_dict(campaign.map),
            "state": _model_to_dict(campaign.state),
            "actors": actors_payload,
            "positions": positions,
            "hp": hp,
            "character_states": character_states,
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
        "For move tool_calls, args must include to_area_id and may include actor_id; do NOT include from_area_id. "
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
        "to_area_id must come from the user's specified target; actor_id may be omitted "
        "to use Context.selected.active_actor_id; from_area_id is derived by the backend "
        "from Context.actors[...].position and MUST NOT be included): "
        "{\"assistant_text\":\"\",\"dialog_type\":\"scene_description\","
        "\"tool_calls\":[{\"id\":\"call_move_1\",\"tool\":\"move\",\"args\":"
        "{\"actor_id\":\"pc_001\",\"to_area_id\":\"area_002\"}}]} "
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


def _enforce_dialog_type_guard(value: object, *, strict_mode: bool) -> None:
    if not strict_mode:
        return
    if not isinstance(value, str):
        return
    normalized = value.strip().lower()
    if not normalized:
        return
    if normalized in DIALOG_TYPES:
        return
    raise SemanticGuardError(f"invalid dialog_type in strict mode: {value}")


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
    (
        positions,
        positions_parent,
        positions_child,
        hp,
        character_states,
    ) = _derive_character_state_maps(campaign)
    state_summary.positions = positions
    state_summary.positions_parent = positions_parent
    state_summary.positions_child = positions_child
    state_summary.hp = hp
    state_summary.character_states = character_states
    return {
        "narrative_text": "",
        "dialog_type": dialog_type,
        "tool_calls": [],
        "applied_actions": [],
        "tool_feedback": None,
        "conflict_report": _model_to_dict(conflict_report),
        "state_summary": _model_to_dict(state_summary),
    }


def _assert_turn_writable(campaign: Campaign, active_actor_id: str) -> None:
    if campaign.lifecycle.ended:
        reason = campaign.lifecycle.reason or "ended"
        raise ValueError(f"campaign has ended: {reason}")
    active_state = _CHARACTER_FACADE.get_state(campaign, active_actor_id)
    if active_state.character_state != "unconscious":
        return
    has_actionable_peer = any(
        actor_id != active_actor_id
        and _CHARACTER_FACADE.get_state(campaign, actor_id).character_state == "alive"
        for actor_id in campaign.selected.party_character_ids
    )
    if has_actionable_peer:
        raise ValueError(
            "active actor is unconscious; switch actor via /api/v1/campaign/select_actor."
        )


def _suppress_repeated_illegal_requests(
    repo: FileRepo,
    campaign_id: str,
    tool_calls: List[ToolCall],
) -> tuple[List[ToolCall], List[FailedCall]]:
    blocked_signatures = _load_repeat_illegal_signatures(repo, campaign_id, window=3)
    if not blocked_signatures or not tool_calls:
        return tool_calls, []
    allowed: List[ToolCall] = []
    suppressed: List[FailedCall] = []
    for call in tool_calls:
        signature = _tool_call_signature(call.tool, call.args)
        if signature in blocked_signatures:
            suppressed.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason="repeat_illegal_request",
                )
            )
            continue
        allowed.append(call)
    return allowed, suppressed


def _load_repeat_illegal_signatures(
    repo: FileRepo, campaign_id: str, *, window: int
) -> set[str]:
    # V1.1: single-process assumption. Future lock provider can guard read/write windows.
    rows = repo.read_recent_turn_log_rows(campaign_id, limit=window)
    if len(rows) < window:
        return set()
    per_turn: List[set[str]] = []
    for row in rows:
        structured = row.get("assistant_structured")
        tool_feedback = row.get("tool_feedback")
        if not isinstance(structured, dict) or not isinstance(tool_feedback, dict):
            return set()
        calls = structured.get("tool_calls")
        failed_calls = tool_feedback.get("failed_calls")
        if not isinstance(calls, list) or not isinstance(failed_calls, list):
            return set()
        failed_tools = {
            item.get("tool")
            for item in failed_calls
            if isinstance(item, dict) and isinstance(item.get("tool"), str)
        }
        signatures: set[str] = set()
        for item in calls:
            if not isinstance(item, dict):
                continue
            tool = item.get("tool")
            args = item.get("args")
            if not isinstance(tool, str) or tool not in failed_tools:
                continue
            if not isinstance(args, dict):
                continue
            signatures.add(_tool_call_signature(tool, args))
        if not signatures:
            return set()
        per_turn.append(signatures)
    shared = set(per_turn[0])
    for signatures in per_turn[1:]:
        shared &= signatures
    return shared


def _tool_call_signature(tool: str, args: Dict[str, object]) -> str:
    payload = {"tool": tool, "args": args}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _turn_id_to_number(turn_id: str) -> int:
    if not isinstance(turn_id, str):
        return 0
    if "_" not in turn_id:
        return 0
    suffix = turn_id.split("_", 1)[1]
    if not suffix.isdigit():
        return 0
    return int(suffix)


def _advance_milestone(campaign: Campaign, turn_number: int, retry_count: int) -> bool:
    milestone = campaign.milestone
    changed = False
    if retry_count > 0:
        next_pressure = milestone.pressure + retry_count
        if next_pressure != milestone.pressure:
            milestone.pressure = next_pressure
            changed = True
    should_advance = False
    if turn_number > 0 and turn_number - milestone.last_advanced_turn >= max(
        1, milestone.turn_trigger_interval
    ):
        should_advance = True
    if milestone.pressure >= max(1, milestone.pressure_threshold):
        should_advance = True
    if not should_advance:
        return changed
    next_current = _next_milestone_label(milestone.current)
    if next_current != milestone.current:
        milestone.current = next_current
        changed = True
    if milestone.last_advanced_turn != turn_number:
        milestone.last_advanced_turn = turn_number
        changed = True
    if milestone.pressure != 0:
        milestone.pressure = 0
        changed = True
    if milestone.summary != "":
        milestone.summary = ""
        changed = True
    return changed


def _next_milestone_label(current: str) -> str:
    if current == "intro":
        return "milestone_1"
    if current.startswith("milestone_"):
        number = current.replace("milestone_", "", 1)
        if number.isdigit():
            return f"milestone_{int(number) + 1}"
    return "milestone_1"


def _mark_ended_if_needed(campaign: Campaign) -> bool:
    if campaign.lifecycle.ended:
        return False
    reason = _compute_end_reason(campaign)
    if reason is None:
        return False
    campaign.lifecycle.ended = True
    campaign.lifecycle.reason = reason
    campaign.lifecycle.ended_at = datetime.now(timezone.utc).isoformat()
    return True


def _compute_end_reason(campaign: Campaign) -> Optional[str]:
    goal_status = campaign.goal.status.strip().lower()
    if goal_status in {"achieved", "goal_achieved", "completed"}:
        return "goal_achieved"

    party_states = [
        _CHARACTER_FACADE.get_state(campaign, actor_id).character_state
        for actor_id in campaign.selected.party_character_ids
    ]
    if not party_states:
        return None
    if all(state == "restrained_permanent" for state in party_states):
        return "restrained_permanent"
    if all(state in {"dead", "dying"} for state in party_states):
        return "party_dead"
    return None
