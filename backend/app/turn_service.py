from __future__ import annotations

import json
import hashlib
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.character_facade_factory import create_runtime_character_facade
from backend.app.conflict_detector import detect_conflicts
from backend.app.debug_resources import build_resources_payload
from backend.app.scenario_runtime_mapper import build_runtime_bootstrap_from_world
from backend.app.scene_entities import build_area_local_entity_views
from backend.app.tool_executor import execute_tool_calls
from backend.app.world_presets import build_campaign_world_preset, build_world_preset
from backend.domain.character_access import (
    CharacterState,
)
from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE, DIALOG_TYPES
from backend.domain.map_models import normalize_map
from backend.domain.models import (
    AppliedAction,
    AssistantStructured,
    Campaign,
    CampaignSummary,
    ConflictReport,
    Goal,
    FailedCall,
    ActorState,
    Entity,
    EntityLocation,
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
from backend.infra.item_catalog import load_item_catalog
from backend.infra.llm_client import LLMClient
from backend.infra.resource_loader import (
    LoadedFlow,
    LoadedPolicy,
    LoadedSchema,
    LoadedTemplate,
    ResourceLoaderError,
    load_enabled_flow,
    load_enabled_policy,
    load_enabled_prompt,
    load_enabled_schema,
    load_enabled_template,
    render_prompt,
)

_CHARACTER_FACADE = create_runtime_character_facade()
_TURN_PROMPT_NAME = "turn_profile_default"
_TURN_FLOW_NAME = "play_turn_basic"
_TURN_SCHEMA_NAMES = ("campaign_selected", "character_fact", "debug_resources_v1")
_TURN_TEMPLATE_NAMES = ("campaign_stub", "character_fact_stub")
_TURN_POLICY_NAMES = ("turn_tool_policy",)
_CREATE_CAMPAIGN_TEMPLATE_NAME = "campaign_stub"


class SemanticGuardError(ValueError):
    pass


class CampaignBusyError(RuntimeError):
    pass


def _normalize_actor_id(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_item_id(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_effective_actor_id(
    campaign: Campaign,
    *,
    execution_actor_id: Optional[str],
    actor_id: Optional[str],
) -> str:
    return (
        _normalize_actor_id(execution_actor_id)
        or _normalize_actor_id(actor_id)
        or campaign.selected.active_actor_id
    )


def _builtin_turn_prompt_template() -> str:
    return (
        "You are the AI GM. Output JSON with keys 'assistant_text', 'dialog_type', and 'tool_calls'. "
        "The world state is authoritative and can change only via tool_calls. "
        "Movement is a state change. If you narrate that an actor moved/entered/arrived/left/changed location, "
        "you MUST include a 'move' tool_call in the same response. "
        "Inventory gain is a state change. If you narrate gaining/obtaining/receiving/picking up an item, "
        "you MUST include an 'inventory_add' tool_call in the same response. "
        "HP change is a state change. If you narrate injury/damage/healing/recovery, "
        "you MUST include an 'hp_delta' tool_call in the same response. "
        "For non-move scene interactions (inspect/talk/open/search/take/drop/detach/use/wait), "
        "prefer one 'scene_action' tool_call with args {actor_id, action, target_id, params}. "
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
        "assistant_text may be empty ONLY when you are making a tool call. "
        "For questions like 'Can I move?' or 'Where can I go?', call 'move_options' and list the returned "
        "1-hop options; explicitly state that no movement has happened yet. "
        "Examples (JSON outputs, schema-accurate). "
        "Example 1 (move intent is explicit and IDs are known; assistant_text empty; "
        "to_area_id must come from the user's specified target; actor_id may be omitted "
        "to use Context.effective_actor_id; from_area_id is derived by the backend "
        "from Context.actors[...].position and MUST NOT be included): "
        "{\"assistant_text\":\"\",\"dialog_type\":\"scene_description\","
        "\"tool_calls\":[{\"id\":\"call_move_1\",\"tool\":\"move\",\"args\":"
        "{\"actor_id\":\"pc_001\",\"to_area_id\":\"area_002\"}}]} "
        "Example 2 (target unclear or user asks where they can go; use move_options; no movement yet; "
        "actor_id should come from Context.effective_actor_id): "
        "{\"assistant_text\":\"No movement yet. I will fetch 1-hop options.\","
        "\"dialog_type\":\"scene_description\","
        "\"tool_calls\":[{\"id\":\"call_move_options_1\",\"tool\":\"move_options\",\"args\":"
        "{\"actor_id\":\"pc_001\"}}]} "
        "Example 3 (no tool call required; MUST respond with non-empty assistant_text): "
        "{\"assistant_text\":\"You are currently in area_002. The corridor is quiet. What do you do next?\","
        "\"dialog_type\":\"scene_description\",\"tool_calls\":[]} "
        "For descriptive character facts, prioritize Context.adopted_profiles_by_actor[actor_id] "
        "when present; otherwise fallback to Context.actors[actor_id].meta. "
        "Do not modify rules, maps, or character sheets. "
        "Context: {{CONTEXT_JSON}}"
    )


def _load_turn_prompt(repo: FileRepo) -> Dict[str, object]:
    repo_root = repo.storage_root.parent
    try:
        loaded = load_enabled_prompt(_TURN_PROMPT_NAME, repo_root=repo_root)
        return {
            "name": loaded.name,
            "version": loaded.version,
            "source_hash": loaded.source_hash,
            "text": loaded.text,
            "fallback": False,
        }
    except ResourceLoaderError:
        fallback_text = _builtin_turn_prompt_template()
        return {
            "name": _TURN_PROMPT_NAME,
            "version": "builtin-v1",
            "source_hash": hashlib.sha256(fallback_text.encode("utf-8")).hexdigest(),
            "text": fallback_text,
            "fallback": True,
        }


def _builtin_turn_flow_descriptor() -> Dict[str, object]:
    return {
        "id": _TURN_FLOW_NAME,
        "version": "builtin-v1",
        "steps": [
            {"id": "prompt_render", "kind": "prompt_render"},
            {"id": "chat_turn", "kind": "chat_turn"},
            {"id": "apply_tools", "kind": "apply_tools"},
            {"id": "state_refresh", "kind": "state_refresh"},
        ],
        "notes": "Built-in descriptor for fallback/debug only.",
    }


def _load_turn_flow(repo: FileRepo) -> Dict[str, object]:
    repo_root = repo.storage_root.parent
    try:
        loaded: LoadedFlow = load_enabled_flow(_TURN_FLOW_NAME, repo_root=repo_root)
        return {
            "name": loaded.name,
            "version": loaded.version,
            "source_hash": loaded.source_hash,
            "content": loaded.content,
            "fallback": False,
        }
    except ResourceLoaderError:
        fallback_content = _builtin_turn_flow_descriptor()
        raw_json = json.dumps(
            fallback_content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return {
            "name": _TURN_FLOW_NAME,
            "version": "builtin-v1",
            "source_hash": hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
            "content": fallback_content,
            "fallback": True,
        }


def _builtin_turn_schema_descriptor(name: str) -> Dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{name} fallback trace schema",
        "type": "object",
    }


def _load_turn_schema(repo: FileRepo, schema_name: str) -> Dict[str, object]:
    repo_root = repo.storage_root.parent
    try:
        loaded: LoadedSchema = load_enabled_schema(schema_name, repo_root=repo_root)
        return {
            "name": loaded.name,
            "version": loaded.version,
            "source_hash": loaded.source_hash,
            "content": loaded.content,
            "fallback": False,
        }
    except ResourceLoaderError:
        fallback_content = _builtin_turn_schema_descriptor(schema_name)
        raw_json = json.dumps(
            fallback_content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return {
            "name": schema_name,
            "version": "builtin-v1",
            "source_hash": hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
            "content": fallback_content,
            "fallback": True,
        }


def _load_turn_schemas(repo: FileRepo) -> List[Dict[str, object]]:
    return [_load_turn_schema(repo, name) for name in _TURN_SCHEMA_NAMES]


def _builtin_turn_template_descriptor(name: str) -> Dict[str, object]:
    return {
        "_comment": f"{name} fallback template for trace only",
        "name": name,
    }


def _load_turn_template(repo: FileRepo, template_name: str) -> Dict[str, object]:
    repo_root = repo.storage_root.parent
    try:
        loaded: LoadedTemplate = load_enabled_template(template_name, repo_root=repo_root)
        return {
            "name": loaded.name,
            "version": loaded.version,
            "source_hash": loaded.source_hash,
            "content": loaded.content,
            "fallback": False,
        }
    except ResourceLoaderError:
        fallback_content = _builtin_turn_template_descriptor(template_name)
        raw_json = json.dumps(
            fallback_content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return {
            "name": template_name,
            "version": "builtin-v1",
            "source_hash": hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
            "content": fallback_content,
            "fallback": True,
        }


def _load_turn_templates(repo: FileRepo) -> List[Dict[str, object]]:
    return [_load_turn_template(repo, name) for name in _TURN_TEMPLATE_NAMES]


def _load_turn_policy(repo: FileRepo, policy_name: str) -> Dict[str, object]:
    repo_root = repo.storage_root.parent
    loaded: LoadedPolicy = load_enabled_policy(policy_name, repo_root=repo_root)
    return {
        "name": loaded.name,
        "version": loaded.version,
        "source_hash": loaded.source_hash,
        "content": loaded.content,
        "fallback": loaded.fallback,
    }


def _load_turn_policies(repo: FileRepo) -> List[Dict[str, object]]:
    return [_load_turn_policy(repo, name) for name in _TURN_POLICY_NAMES]


def _load_campaign_selected_template(
    repo: FileRepo,
) -> tuple[Dict[str, object], Dict[str, object]]:
    repo_root = repo.storage_root.parent
    try:
        loaded: LoadedTemplate = load_enabled_template(
            _CREATE_CAMPAIGN_TEMPLATE_NAME, repo_root=repo_root
        )
        content = loaded.content if isinstance(loaded.content, dict) else {}
        selected = content.get("selected") if isinstance(content.get("selected"), dict) else {}
        defaults: Dict[str, object] = {}
        party = selected.get("party_character_ids")
        if isinstance(party, list) and all(isinstance(item, str) for item in party):
            defaults["party_character_ids"] = list(party)
        active = selected.get("active_actor_id")
        if isinstance(active, str):
            defaults["active_actor_id"] = active
        return (
            defaults,
            {
                "name": loaded.name,
                "version": loaded.version,
                "hash": loaded.source_hash,
                "fallback": False,
            },
        )
    except ResourceLoaderError:
        return (
            {},
            {
                "name": _CREATE_CAMPAIGN_TEMPLATE_NAME,
                "version": "builtin-v1",
                "hash": "",
                "fallback": True,
            },
        )


def _resolve_selected_defaults(
    *,
    party_character_ids: Optional[List[str]],
    active_actor_id: Optional[str],
    template_defaults: Dict[str, object],
) -> tuple[List[str], str, bool]:
    applied = False

    party_candidate = party_character_ids
    if party_candidate is None and "party_character_ids" in template_defaults:
        raw_party = template_defaults.get("party_character_ids")
        if isinstance(raw_party, list) and all(isinstance(item, str) for item in raw_party):
            party_candidate = list(raw_party)
            applied = True

    active_candidate = active_actor_id
    if active_candidate is None and "active_actor_id" in template_defaults:
        raw_active = template_defaults.get("active_actor_id")
        if isinstance(raw_active, str):
            active_candidate = raw_active
            applied = True

    resolved_party = party_candidate or ["pc_001"]
    resolved_active = active_candidate or resolved_party[0]
    if resolved_active not in resolved_party:
        resolved_party = [resolved_active] + resolved_party

    return list(resolved_party), resolved_active, applied


class CampaignTurnLockRegistry:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}

    def try_acquire(self, campaign_id: str) -> Optional[threading.Lock]:
        with self._guard:
            lock = self._locks.get(campaign_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[campaign_id] = lock
        if not lock.acquire(blocking=False):
            return None
        return lock

    def release(self, lock: threading.Lock) -> None:
        lock.release()


_CAMPAIGN_TURN_LOCKS = CampaignTurnLockRegistry()


class TurnService:
    def __init__(self, repo: FileRepo) -> None:
        self.repo = repo
        self.llm: Optional[LLMClient] = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def create_campaign(
        self,
        world_id: str,
        map_id: str,
        party_character_ids: Optional[List[str]],
        active_actor_id: Optional[str],
    ) -> str:
        campaign_id, _, _ = self.create_campaign_with_template_usage(
            world_id=world_id,
            map_id=map_id,
            party_character_ids=party_character_ids,
            active_actor_id=active_actor_id,
        )
        return campaign_id

    def create_campaign_with_template_usage(
        self,
        world_id: str,
        map_id: str,
        party_character_ids: Optional[List[str]],
        active_actor_id: Optional[str],
    ) -> tuple[str, Dict[str, object], bool]:
        campaign_id = self.repo.next_campaign_id()
        selected_defaults, template_usage = _load_campaign_selected_template(self.repo)
        resolved_party, resolved_active, applied = _resolve_selected_defaults(
            party_character_ids=party_character_ids,
            active_actor_id=active_actor_id,
            template_defaults=selected_defaults,
        )
        template_usage["applied"] = applied
        bootstrap = _build_campaign_bootstrap(world_id, self.repo)
        actors = {
            character_id: ActorState(
                position=bootstrap["start_area_id"],
                hp=DEFAULT_HP,
                character_state=DEFAULT_CHARACTER_STATE,
                meta={},
            )
            for character_id in resolved_party
        }
        if resolved_active not in actors:
            actors[resolved_active] = ActorState(
                position=bootstrap["start_area_id"],
                hp=DEFAULT_HP,
                character_state=DEFAULT_CHARACTER_STATE,
                meta={},
            )
        selected = Selected(
            world_id=world_id,
            map_id=map_id,
            party_character_ids=resolved_party,
            active_actor_id=resolved_active,
        )
        campaign = Campaign(
            id=campaign_id,
            selected=selected,
            settings_snapshot=SettingsSnapshot(),
            goal=Goal(text=bootstrap["goal_text"], status="active"),
            milestone=Milestone(current="intro", last_advanced_turn=0),
            map=bootstrap["map"],
            actors=actors,
            entities=bootstrap["entities"],
        )
        normalize_map(campaign.map)
        self.repo.create_campaign(campaign)
        trace_enabled = bool(
            campaign.settings_snapshot.dialog.turn_profile_trace_enabled
        )
        return campaign_id, template_usage, trace_enabled

    def list_campaigns(self) -> List[CampaignSummary]:
        return self.repo.list_campaigns()

    def select_actor(self, campaign_id: str, actor_id: str) -> Campaign:
        campaign = self.repo.get_campaign(campaign_id)
        if actor_id not in campaign.selected.party_character_ids:
            raise ValueError("actor_id not in party_character_ids")
        return self.repo.update_active_actor(campaign, actor_id)

    def submit_turn(
        self,
        campaign_id: str,
        user_input: str,
        actor_id: Optional[str] = None,
        *,
        execution_actor_id: Optional[str] = None,
        selected_item_id: Optional[str] = None,
    ) -> Dict[str, object]:
        campaign_lock = _CAMPAIGN_TURN_LOCKS.try_acquire(campaign_id)
        if campaign_lock is None:
            raise CampaignBusyError(
                "turn_in_progress: campaign turn is already running; wait and retry."
            )
        try:
            campaign = self.repo.get_campaign(campaign_id)
            state_updated = _ensure_minimum_state(campaign, self.repo)
            if state_updated:
                self.repo.save_campaign(campaign)
            effective_actor_id = _resolve_effective_actor_id(
                campaign,
                execution_actor_id=execution_actor_id,
                actor_id=actor_id,
            )
            if effective_actor_id not in campaign.selected.party_character_ids:
                raise ValueError("actor_id not in party_character_ids")
            if _mark_ended_if_needed(campaign):
                self.repo.save_campaign(campaign)
            _assert_turn_writable(campaign, effective_actor_id)
            selected_item = _resolve_selected_item_context(
                campaign,
                effective_actor_id,
                selected_item_id=selected_item_id,
                repo_root=self.repo.storage_root.parent,
            )
            turn_prompt = _load_turn_prompt(self.repo)
            turn_flow = _load_turn_flow(self.repo)
            system_prompt = _build_system_prompt(
                campaign,
                effective_actor_id,
                prompt_template=str(turn_prompt["text"]),
                selected_item=selected_item,
            )
            turn_prompt["rendered_hash"] = hashlib.sha256(
                system_prompt.encode("utf-8")
            ).hexdigest()
            turn_prompt["variables"] = ["CONTEXT_JSON"]
            flow_json = json.dumps(
                turn_flow.get("content", {}),
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            )
            turn_flow["rendered_hash"] = hashlib.sha256(flow_json.encode("utf-8")).hexdigest()
            turn_schemas = (
                _load_turn_schemas(self.repo)
                if campaign.settings_snapshot.dialog.turn_profile_trace_enabled
                else []
            )
            turn_templates = (
                _load_turn_templates(self.repo)
                if campaign.settings_snapshot.dialog.turn_profile_trace_enabled
                else []
            )
            turn_policies = (
                _load_turn_policies(self.repo)
                if campaign.settings_snapshot.dialog.turn_profile_trace_enabled
                else []
            )
            response_debug = (
                _build_turn_debug_payload(
                    campaign,
                    effective_actor_id,
                    turn_prompt,
                    turn_flow,
                    turn_schemas,
                    turn_templates,
                    turn_policies,
                    selected_item=selected_item,
                )
                if campaign.settings_snapshot.dialog.turn_profile_trace_enabled
                else None
            )
            retry_count = 0
            last_conflicts = []
            debug_append = None
            max_retries = 2

            while True:
                llm_output = self._get_llm().generate(
                    system_prompt, user_input, debug_append
                )
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
                    campaign, effective_actor_id, tool_calls, repo=self.repo
                )
                if suppressed_failed_calls:
                    failed_calls = list(suppressed_failed_calls)
                    if tool_feedback:
                        failed_calls.extend(tool_feedback.failed_calls)
                    tool_feedback = ToolFeedback(failed_calls=failed_calls)
                state_after = _state_summary_dict(
                    campaign, active_actor_id=effective_actor_id
                )
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
                        conflict_report,
                        campaign,
                        effective_actor_id,
                        dialog_type,
                        debug_payload=response_debug,
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
                assistant_text = _normalize_authoritative_assistant_text(
                    llm_output.get("assistant_text", ""),
                    applied_actions,
                    tool_feedback,
                )
                entry = TurnLogEntry(
                    turn_id=turn_id,
                    timestamp=timestamp,
                    user_input=user_input,
                    dialog_type=dialog_type,
                    dialog_type_source=dialog_type_source,
                    settings_revision=campaign.settings_revision,
                    assistant_text=assistant_text,
                    assistant_structured=AssistantStructured(tool_calls=tool_calls),
                    applied_actions=applied_actions,
                    tool_feedback=tool_feedback,
                    conflict_report=conflict_report,
                    state_summary=StateSummary(active_actor_id=effective_actor_id),
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
                entry.state_summary.inventories = _all_actor_inventories(campaign)
                entry.state_summary.objective = campaign.goal.text.strip()
                (
                    entry.state_summary.active_area_id,
                    entry.state_summary.active_area_name,
                    entry.state_summary.active_area_description,
                ) = _active_area_context(campaign, effective_actor_id)
                entry.state_summary.active_actor_inventory = _active_actor_inventory(
                    campaign, effective_actor_id
                )
                self.repo.append_turn_log(campaign_id, entry)
                return _build_success_response(
                    entry,
                    tool_calls,
                    applied_actions,
                    tool_feedback,
                    effective_actor_id=effective_actor_id,
                    debug_payload=response_debug,
                )
        finally:
            _CAMPAIGN_TURN_LOCKS.release(campaign_lock)


def _default_starter_map() -> MapData:
    return MapData(
        areas={
            "area_001": MapArea(
                id="area_001",
                name="Starting Area",
                description="A quiet checkpoint lit by a flickering lantern.",
                reachable_area_ids=["area_002"],
            ),
            "area_002": MapArea(
                id="area_002",
                name="Side Room",
                description="A cramped side room with scattered crates.",
                reachable_area_ids=[],
            ),
        },
        connections=[],
    )


def _starter_entities() -> Dict[str, Entity]:
    return {
        "door_01": Entity(
            id="door_01",
            kind="object",
            label="Rusty Door",
            tags=["door", "metal"],
            loc=EntityLocation(type="area", id="area_001"),
            verbs=["inspect", "open", "force", "detach"],
            state={"locked": True, "opened": False},
            props={"mass": 40, "size": "large"},
        ),
        "crate_01": Entity(
            id="crate_01",
            kind="container",
            label="Old Crate",
            tags=["container", "wood"],
            loc=EntityLocation(type="area", id="area_001"),
            verbs=["inspect", "open", "search", "take"],
            state={"locked": False, "opened": False},
            props={"mass": 12, "size": "medium"},
        ),
        "npc_guide_01": Entity(
            id="npc_guide_01",
            kind="npc",
            label="Wary Guide",
            tags=["npc", "guide"],
            loc=EntityLocation(type="area", id="area_001"),
            verbs=["inspect", "talk"],
            state={},
            props={"mass": 70, "size": "medium"},
        ),
    }


def _build_campaign_bootstrap(
    world_id: str,
    repo: Optional[FileRepo] = None,
) -> Dict[str, object]:
    world = repo.get_world(world_id) if repo is not None else None
    if world is None:
        world = build_world_preset(world_id)
    if world is not None:
        # Guarded v0 path: only supported scenario-generator metadata-backed
        # worlds, including the built-in dev preset, go through the
        # internal scenario chain here.
        scenario_bootstrap = build_runtime_bootstrap_from_world(world)
        if scenario_bootstrap is not None:
            return {
                "start_area_id": scenario_bootstrap.start_area_id,
                "goal_text": scenario_bootstrap.goal_text,
                "map": scenario_bootstrap.map_data,
                "entities": scenario_bootstrap.entities,
            }
    preset = build_campaign_world_preset(world_id)
    if preset is not None:
        return {
            "start_area_id": preset.start_area_id,
            "goal_text": preset.goal_text,
            "map": preset.map_data,
            "entities": preset.entities,
        }
    return {
        "start_area_id": "area_001",
        "goal_text": "Define the main objective",
        "map": _default_starter_map(),
        "entities": _starter_entities(),
    }


def _ensure_minimum_state(
    campaign: Campaign,
    repo: Optional[FileRepo] = None,
) -> bool:
    updated = False
    if not isinstance(campaign.entities, dict):
        campaign.entities = {}
        updated = True
    if not campaign.map.areas:
        bootstrap = _build_campaign_bootstrap(campaign.selected.world_id, repo)
        campaign.map = bootstrap["map"]
        if not campaign.entities:
            campaign.entities = bootstrap["entities"]
        if not campaign.goal.text.strip():
            campaign.goal.text = str(bootstrap["goal_text"])
        updated = True
    start_area_id = next(iter(campaign.map.areas.keys()), "area_001")
    bootstrap = _build_campaign_bootstrap(campaign.selected.world_id, repo)
    if isinstance(bootstrap.get("start_area_id"), str) and bootstrap["start_area_id"] in campaign.map.areas:
        start_area_id = str(bootstrap["start_area_id"])
    for character_id in campaign.selected.party_character_ids:
        state = _CHARACTER_FACADE.get_state(campaign, character_id)
        if state.position is None:
            _CHARACTER_FACADE.set_state(
                campaign,
                character_id,
                CharacterState(
                    position=start_area_id,
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
        "entities": deepcopy(campaign.entities),
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
    campaign.entities = snapshot["entities"]
    campaign.state = snapshot["state"]
    campaign.positions = snapshot["campaign_positions"]
    campaign.hp = snapshot["campaign_hp"]
    campaign.character_states = snapshot["campaign_character_states"]
    campaign.map = snapshot["map"]


def _state_summary_dict(
    campaign: Campaign, active_actor_id: Optional[str] = None
) -> Dict[str, object]:
    (
        positions,
        positions_parent,
        positions_child,
        hp,
        character_states,
    ) = _derive_character_state_maps(campaign)
    resolved_actor_id = active_actor_id or campaign.selected.active_actor_id
    active_area_id, active_area_name, active_area_description = _active_area_context(
        campaign, resolved_actor_id
    )
    return {
        "positions": positions,
        "positions_parent": positions_parent,
        "positions_child": positions_child,
        "hp": hp,
        "character_states": character_states,
        "inventories": _all_actor_inventories(campaign),
        "objective": campaign.goal.text.strip(),
        "active_area_id": active_area_id,
        "active_area_name": active_area_name,
        "active_area_description": active_area_description,
        "active_actor_inventory": _active_actor_inventory(campaign, resolved_actor_id),
    }


def _derive_character_state_maps(campaign: Campaign) -> tuple[
    Dict[str, str],
    Dict[str, str],
    Dict[str, Optional[str]],
    Dict[str, int],
    Dict[str, str],
]:
    return _CHARACTER_FACADE.build_state_maps(campaign)


def _build_actor_prompt_payloads(
    campaign: Campaign,
) -> tuple[Dict[str, Dict[str, object]], Dict[str, Dict[str, object]]]:
    actors_payload: Dict[str, Dict[str, object]] = {}
    adopted_profiles_by_actor: Dict[str, Dict[str, object]] = {}
    for actor_id in sorted(campaign.actors.keys()):
        actor = campaign.actors[actor_id]
        actor_meta = actor.meta if isinstance(actor.meta, dict) else {}
        meta_payload = _sanitize_actor_meta_for_prompt(actor_meta)
        actors_payload[actor_id] = {
            "position": actor.position,
            "hp": actor.hp,
            "character_state": actor.character_state,
            "inventory": _active_actor_inventory(campaign, actor_id),
            "meta": meta_payload,
        }
        profile_payload = actor_meta.get("profile")
        if isinstance(profile_payload, dict):
            adopted_profiles_by_actor[actor_id] = dict(profile_payload)
    return actors_payload, adopted_profiles_by_actor


_PROMPT_INTERNAL_META_KEYS = {
    "accepted_at",
    "accepted_by",
    "character_id",
    "created_at",
    "debug",
    "diagnostics",
    "profile_hash",
    "request_id",
    "schema_version",
    "source_draft_ref",
    "trace",
    "updated_at",
}
_PROMPT_INTERNAL_META_PREFIXES = ("debug_", "diag_", "diagnostic_", "internal_", "sidecar_", "trace_")
_PROMPT_INTERNAL_META_SUFFIXES = ("_at", "_hash")


def _sanitize_actor_meta_for_prompt(actor_meta: Dict[str, object]) -> Dict[str, object]:
    payload: Dict[str, object] = {}
    for key, value in actor_meta.items():
        if key == "profile":
            continue
        if not isinstance(key, str):
            payload[key] = value
            continue
        normalized = key.strip().lower()
        if not normalized:
            continue
        if normalized in _PROMPT_INTERNAL_META_KEYS:
            continue
        if any(normalized.startswith(prefix) for prefix in _PROMPT_INTERNAL_META_PREFIXES):
            continue
        if any(normalized.endswith(suffix) for suffix in _PROMPT_INTERNAL_META_SUFFIXES):
            continue
        payload[key] = value
    return payload


def _scene_prompt_payload(campaign: Campaign, actor_id: str) -> Dict[str, object]:
    active_state = _CHARACTER_FACADE.get_state(campaign, actor_id)
    area_id = active_state.position if isinstance(active_state.position, str) else None
    return {
        "active_area_id": area_id,
        "entities_in_area": build_area_local_entity_views(campaign, area_id),
    }


def _build_system_prompt(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    prompt_template: str,
    selected_item: Optional[Dict[str, object]] = None,
) -> str:
    positions, _, _, hp, character_states = _derive_character_state_maps(campaign)
    actors_payload, adopted_profiles_by_actor = _build_actor_prompt_payloads(campaign)
    compress_enabled = campaign.settings_snapshot.context.compress_enabled
    if compress_enabled:
        active_state = _CHARACTER_FACADE.get_state(campaign, effective_actor_id)
        _, active_area_name, active_area_description = _active_area_context(
            campaign, effective_actor_id
        )
        payload = {
            "context_mode": "compressed",
            "dialog_types": DIALOG_TYPES,
            "default_dialog_type": DEFAULT_DIALOG_TYPE,
            "allowlist": campaign.allowlist,
            "effective_actor_id": effective_actor_id,
            "selected": _model_to_dict(campaign.selected),
            "settings_snapshot": _model_to_dict(campaign.settings_snapshot),
            "goal": _model_to_dict(campaign.goal),
            "lifecycle": _model_to_dict(campaign.lifecycle),
            "milestone": _model_to_dict(campaign.milestone),
            "map_summary": {
                "area_count": len(campaign.map.areas),
                "active_actor_area_id": active_state.position,
                "active_area_name": active_area_name,
                "active_area_description": active_area_description,
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
            "active_actor_inventory": _active_actor_inventory(
                campaign, effective_actor_id
            ),
            "scene": _scene_prompt_payload(campaign, effective_actor_id),
            "adopted_profiles_by_actor": adopted_profiles_by_actor,
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
            "effective_actor_id": effective_actor_id,
            "selected": _model_to_dict(campaign.selected),
            "settings_snapshot": _model_to_dict(campaign.settings_snapshot),
            "goal": _model_to_dict(campaign.goal),
            "lifecycle": _model_to_dict(campaign.lifecycle),
            "milestone": _model_to_dict(campaign.milestone),
            "map": _model_to_dict(campaign.map),
            "state": _model_to_dict(campaign.state),
            "actors": actors_payload,
            "scene": _scene_prompt_payload(campaign, effective_actor_id),
            "adopted_profiles_by_actor": adopted_profiles_by_actor,
            "positions": positions,
            "hp": hp,
            "character_states": character_states,
            "response_format": {
                "assistant_text": "string narrative",
                "dialog_type": "one of dialog_types",
                "tool_calls": "array of tool calls",
            },
        }
    if selected_item:
        payload["selected_item"] = dict(selected_item)
    context_json = json.dumps(payload, ensure_ascii=False)
    try:
        return render_prompt(
            prompt_template,
            {"CONTEXT_JSON": context_json},
            allowlist={"CONTEXT_JSON"},
        )
    except ResourceLoaderError:
        # Keep runtime behavior stable: malformed external prompt falls back inline.
        builtin = _builtin_turn_prompt_template()
        return render_prompt(
            builtin,
            {"CONTEXT_JSON": context_json},
            allowlist={"CONTEXT_JSON"},
        )


def _build_turn_debug_payload(
    campaign: Campaign,
    active_actor_id: str,
    prompt_resource: Dict[str, object],
    flow_resource: Dict[str, object],
    schema_resources: List[Dict[str, object]],
    template_resources: List[Dict[str, object]],
    policy_resources: List[Dict[str, object]],
    selected_item: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    _, adopted_profiles_by_actor = _build_actor_prompt_payloads(campaign)
    encoded = json.dumps(
        adopted_profiles_by_actor,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    prompt_variables_obj = prompt_resource.get("variables", [])
    prompt_variables = (
        [item for item in prompt_variables_obj if isinstance(item, str)]
        if isinstance(prompt_variables_obj, list)
        else []
    )
    prompt_entry = {
        "name": str(prompt_resource.get("name", _TURN_PROMPT_NAME)),
        "version": str(prompt_resource.get("version", "builtin-v1")),
        "source_hash": str(prompt_resource.get("source_hash", "")),
        "rendered_hash": str(prompt_resource.get("rendered_hash", "")),
        "fallback": bool(prompt_resource.get("fallback")),
    }
    flow_entry = {
        "name": str(flow_resource.get("name", _TURN_FLOW_NAME)),
        "version": str(flow_resource.get("version", "builtin-v1")),
        "hash": str(flow_resource.get("source_hash", "")),
        "fallback": bool(flow_resource.get("fallback")),
    }
    schema_entries = [
        {
            "name": str(item.get("name", "")),
            "version": str(item.get("version", "builtin-v1")),
            "hash": str(item.get("source_hash", "")),
            "fallback": bool(item.get("fallback")),
        }
        for item in schema_resources
        if isinstance(item, dict)
    ]
    template_entries = [
        {
            "name": str(item.get("name", "")),
            "version": str(item.get("version", "builtin-v1")),
            "hash": str(item.get("source_hash", "")),
            "fallback": bool(item.get("fallback")),
        }
        for item in template_resources
        if isinstance(item, dict)
    ]
    policy_entries = [
        {
            "name": str(item.get("name", "")),
            "version": str(item.get("version", "builtin-v1")),
            "hash": str(item.get("source_hash", "")),
            "fallback": bool(item.get("fallback")),
        }
        for item in policy_resources
        if isinstance(item, dict)
    ]
    resources_payload = build_resources_payload(
        prompts=[prompt_entry],
        flows=[flow_entry],
        schemas=schema_entries,
        templates=template_entries,
        policies=policy_entries,
        template_usage=[],
    )

    payload: Dict[str, object] = {
        "used_profile_hash": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        # legacy flat fields (kept for compatibility)
        "used_prompt_name": prompt_entry["name"],
        "used_prompt_version": prompt_entry["version"],
        "used_prompt_hash": prompt_entry["source_hash"],
        "used_prompt_source_hash": prompt_entry["source_hash"],
        "used_prompt_rendered_hash": prompt_entry.get("rendered_hash", ""),
        "used_prompt_variables": prompt_variables,
        "used_flow_name": flow_entry["name"],
        "used_flow_version": flow_entry["version"],
        "used_flow_hash": flow_entry["hash"],
        # unified structure
        "resources": resources_payload,
    }
    if bool(prompt_entry.get("fallback")):
        payload["used_prompt_fallback"] = True
    if bool(flow_entry.get("fallback")):
        payload["used_flow_fallback"] = True

    # legacy nested fields (kept for compatibility), generated from resources
    payload["prompt"] = {
        **prompt_entry,
        "variables": prompt_variables,
    }
    payload["flow"] = dict(flow_entry)
    payload["schemas"] = resources_payload["schemas"]
    payload["templates"] = resources_payload["templates"]
    active_profile = adopted_profiles_by_actor.get(active_actor_id)
    if isinstance(active_profile, dict):
        version = active_profile.get("schema_version")
        if isinstance(version, str) and version.strip():
            payload["used_profile_version"] = version
    selected_item_debug = _build_selected_item_debug(selected_item)
    if selected_item_debug is not None:
        payload["selected_item"] = selected_item_debug
    return payload


def _build_selected_item_debug(
    selected_item: Optional[Dict[str, object]],
) -> Optional[Dict[str, object]]:
    if not isinstance(selected_item, dict):
        return None
    item_id = selected_item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return None
    return {
        "id": item_id.strip(),
        "has_metadata": bool(
            isinstance(selected_item.get("name"), str)
            or isinstance(selected_item.get("description"), str)
        ),
    }


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
    *,
    effective_actor_id: str,
    debug_payload: Optional[Dict[str, object]] = None,
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
    response = {
        "effective_actor_id": effective_actor_id,
        "narrative_text": entry.assistant_text,
        "dialog_type": entry.dialog_type,
        "tool_calls": tool_calls_payload,
        "applied_actions": applied_actions_payload,
        "tool_feedback": tool_feedback_payload,
        "conflict_report": conflict_report_payload,
        "state_summary": state_summary,
    }
    _apply_move_options_narrative_fallback(response)
    _apply_success_tool_narrative_fallback(response)
    if debug_payload:
        response["debug"] = dict(debug_payload)
    return response


def _normalize_authoritative_assistant_text(
    raw_text: object,
    applied_actions: List[object],
    tool_feedback: object,
) -> str:
    narrative_text = raw_text.strip() if isinstance(raw_text, str) else ""
    failed_calls = (
        tool_feedback.failed_calls
        if isinstance(tool_feedback, ToolFeedback)
        else []
    )
    failed_inventory_add = any(
        isinstance(item, FailedCall) and item.tool == "inventory_add"
        for item in failed_calls
    )
    successful_inventory_add = any(
        isinstance(item, AppliedAction) and item.tool == "inventory_add"
        for item in applied_actions
    )
    if failed_inventory_add and not successful_inventory_add:
        if not applied_actions:
            return "No inventory change happened."
        if _narrative_claims_inventory_gain(narrative_text):
            return ""
    return narrative_text


def _narrative_claims_inventory_gain(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    keywords = [
        "add",
        "added",
        "inventory",
        "pick up",
        "picked up",
        "obtain",
        "obtained",
        "receive",
        "received",
        "find ",
        "found ",
        "take ",
        "took ",
    ]
    return any(keyword in lowered for keyword in keywords)


def _apply_move_options_narrative_fallback(response: Dict[str, object]) -> None:
    if not isinstance(response, dict):
        return
    narrative_text = response.get("narrative_text")
    if isinstance(narrative_text, str) and narrative_text.strip():
        return
    tool_feedback = response.get("tool_feedback")
    if tool_feedback is not None:
        return
    applied_actions = response.get("applied_actions")
    if not isinstance(applied_actions, list) or len(applied_actions) != 1:
        return
    only_action = applied_actions[0]
    if not isinstance(only_action, dict) or only_action.get("tool") != "move_options":
        return
    result = only_action.get("result")
    if not isinstance(result, dict):
        return
    options = result.get("options")
    if not isinstance(options, list):
        return
    labels = []
    for option in options:
        if not isinstance(option, dict):
            continue
        area_id = option.get("to_area_id")
        name = option.get("name")
        if isinstance(area_id, str) and area_id.strip():
            if isinstance(name, str) and name.strip():
                labels.append(f"{name.strip()} ({area_id.strip()})")
            else:
                labels.append(area_id.strip())
    if labels:
        response["narrative_text"] = (
            "No movement happened yet. Reachable areas: " + ", ".join(labels) + "."
        )
    else:
        response["narrative_text"] = (
            "No movement happened yet. No reachable areas are available from the current position."
        )


def _apply_success_tool_narrative_fallback(response: Dict[str, object]) -> None:
    if not isinstance(response, dict):
        return
    narrative_text = response.get("narrative_text")
    if isinstance(narrative_text, str) and narrative_text.strip():
        return
    applied_actions = response.get("applied_actions")
    if not isinstance(applied_actions, list) or not applied_actions:
        return
    if len(applied_actions) == 1 and isinstance(applied_actions[0], dict):
        result = applied_actions[0].get("result")
        if isinstance(result, dict):
            result_narrative = result.get("narrative")
            if isinstance(result_narrative, str) and result_narrative.strip():
                response["narrative_text"] = result_narrative.strip()
                return
    response["narrative_text"] = "The action was performed."


def _build_failure_response(
    conflict_report: ConflictReport,
    campaign: Campaign,
    effective_actor_id: str,
    dialog_type: str,
    debug_payload: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    state_summary = StateSummary(active_actor_id=effective_actor_id)
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
    state_summary.inventories = _all_actor_inventories(campaign)
    state_summary.objective = campaign.goal.text.strip()
    (
        state_summary.active_area_id,
        state_summary.active_area_name,
        state_summary.active_area_description,
    ) = _active_area_context(campaign, effective_actor_id)
    state_summary.active_actor_inventory = _active_actor_inventory(
        campaign, effective_actor_id
    )
    response = {
        "effective_actor_id": effective_actor_id,
        "narrative_text": "",
        "dialog_type": dialog_type,
        "tool_calls": [],
        "applied_actions": [],
        "tool_feedback": None,
        "conflict_report": _model_to_dict(conflict_report),
        "state_summary": _model_to_dict(state_summary),
    }
    if debug_payload:
        response["debug"] = dict(debug_payload)
    return response


def _active_area_context(
    campaign: Campaign, active_actor_id: str
) -> tuple[Optional[str], str, str]:
    actor = campaign.actors.get(active_actor_id)
    if actor is None or not isinstance(actor.position, str):
        return None, "", ""
    area = campaign.map.areas.get(actor.position)
    if area is None:
        return actor.position, "", ""
    return actor.position, area.name, area.description


def _active_actor_inventory(campaign: Campaign, actor_id: str) -> Dict[str, int]:
    actor = campaign.actors.get(actor_id)
    if actor is None or not isinstance(actor.inventory, dict):
        return {}
    inventory: Dict[str, int] = {}
    for item_id, qty in actor.inventory.items():
        if not isinstance(item_id, str):
            continue
        normalized_id = item_id.strip()
        if not normalized_id:
            continue
        if not isinstance(qty, int) or qty <= 0:
            continue
        inventory[normalized_id] = qty
    return inventory


def _resolve_selected_item_context(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    selected_item_id: Optional[str],
    repo_root: Path,
) -> Optional[Dict[str, object]]:
    normalized_item_id = _normalize_item_id(selected_item_id)
    if not normalized_item_id:
        return None
    inventory = _active_actor_inventory(campaign, effective_actor_id)
    quantity = inventory.get(normalized_item_id)
    if not isinstance(quantity, int) or quantity <= 0:
        return None
    selected_item = {
        "id": normalized_item_id,
        "quantity": quantity,
    }
    item_metadata = load_item_catalog(repo_root).get(normalized_item_id, {})
    if isinstance(item_metadata, dict):
        name = item_metadata.get("name")
        description = item_metadata.get("description")
        if isinstance(name, str) and name.strip():
            selected_item["name"] = name.strip()
        if isinstance(description, str) and description.strip():
            selected_item["description"] = description.strip()
    return selected_item


def _all_actor_inventories(campaign: Campaign) -> Dict[str, Dict[str, int]]:
    inventories: Dict[str, Dict[str, int]] = {}
    for actor_id in sorted(campaign.actors.keys()):
        inventories[actor_id] = _active_actor_inventory(campaign, actor_id)
    return inventories


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
