from __future__ import annotations

import json
import hashlib
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.campaign_consequence_service import (
    build_consequence_debug_context,
    build_consequence_prompt_context,
    build_consequence_state_summary,
    refresh_campaign_consequences,
)
from backend.app.campaign_fact_service import (
    build_fact_debug_context,
    build_fact_prompt_context,
    build_npc_memory_context,
    build_npc_memory_debug_context,
    prune_campaign_facts,
    record_npc_memory_fact,
)
from backend.app.campaign_hostility_service import build_hostility_state_summary
from backend.app.campaign_mistake_service import (
    build_mistake_debug_context,
    build_mistake_state_summary,
    record_mistake_signals,
)
from backend.app.character_facade_factory import create_runtime_character_facade
from backend.app.conflict_detector import detect_conflicts
from backend.app.debug_resources import build_resources_payload
from backend.app.item_operations import build_area_root_stack_views
from backend.app.item_runtime import (
    SelectedStackResolution,
    build_actor_inventory_stack_views_from_items_only,
    build_all_actor_inventory_stack_views_from_items_only,
    create_runtime_item_stack,
    derive_actor_inventory_from_items_only,
    derive_all_actor_inventories_from_items_only,
    derive_actor_inventory_stack_ids_from_items_only,
    derive_all_actor_inventory_stack_ids_from_items_only,
    get_actor_item_quantity_from_items_only,
    normalize_campaign_items,
    resolve_selected_stack_resolution,
)
from backend.app.scenario_runtime_mapper import (
    build_runtime_bootstrap_from_world,
    is_scenario_generator_world,
)
from backend.app.scene_entities import build_area_local_entity_views
from backend.app.tool_executor import execute_tool_calls
from backend.app.world_presets import (
    build_campaign_world_preset,
    build_world_preset,
    required_item_for_move,
)
from backend.domain.character_access import (
    CharacterState,
)
from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE, DIALOG_TYPES
from backend.domain.map_models import normalize_map
from backend.domain.mistake_models import CampaignMistakeSignalCreate
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
        "If Context.selected_scene_target is present and the player intent is to take/pick up/grab something, "
        "use that exact target_id in one 'scene_action' take call instead of guessing another pickup target. "
        "Context.selected_scene_target is only a disambiguation hint and does not override scene rules. "
        "If Context.npc_memory is present, use it only as local memory for that specific NPC. "
        "Treat Context.npc_memory as uncertain conversational context, not authoritative world truth, "
        "and do not apply it to other NPCs or to the global scene state. "
        "If Context.consequences is present, use it only as a light world-reaction modifier. "
        "It may make the local atmosphere feel more watchful or make nearby NPCs sound more guarded, "
        "but it must not be treated as a hard lock, branching event, or invented world mutation. "
        "For immediate movement truth, treat Context.movement_rules.reachable_areas as the only areas the actor can enter right now. "
        "If an area appears in Context.movement_rules.blocked_transitions, it is connected but blocked; "
        "describe the obstruction and listed requirement instead of saying the actor can go there now. "
        "When the player asks how to reach a blocked area, explain the block reason and required item truthfully. "
        "Use Context.guidance.blocked_transition_hints to suggest at most one or two plausible leads when the actor is blocked or asks how to reach a blocked area. "
        "Use Context.guidance.idle_suggestions when the player is vague or stuck, and offer at most one or two suggestive directions rather than a checklist. "
        "Use Context.guidance.item_relevance to explain where a carried item may be more relevant when the player tries the wrong item. "
        "Scale directness with Context.guidance.hint_level: level 1 stays broad, level 2 can focus on a likely area or source, and level 3 can foreground the strongest lead without turning it into an instruction or walkthrough. "
        "Avoid imperative phrasing such as 'You should', 'Go to', 'Search', or 'Use X on Y' when giving guidance. "
        "Do not invent sources or instructions that are not supported by Context.guidance. "
        "Take only works on targets that are currently visible and takeable. Search may reveal hidden items before they can be taken. "
        "If the player tries to take from a searchable container or clue source, guide them to search first. "
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
            items=bootstrap["items"],
            entities=bootstrap["entities"],
            scenario_runtime_fragment=bootstrap.get("scenario_runtime_fragment"),
        )
        normalize_map(campaign.map)
        normalize_campaign_items(campaign)
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
        selected_stack_id: Optional[str] = None,
        selected_item_id: Optional[str] = None,
        selected_target_id: Optional[str] = None,
    ) -> Dict[str, object]:
        campaign_lock = _CAMPAIGN_TURN_LOCKS.try_acquire(campaign_id)
        if campaign_lock is None:
            raise CampaignBusyError(
                "turn_in_progress: campaign turn is already running; wait and retry."
            )
        try:
            campaign = self.repo.get_campaign(campaign_id)
            state_updated = _ensure_minimum_state(campaign, self.repo)
            current_turn_index = _turn_id_to_number(self.repo.next_turn_id(campaign_id))
            pruned_fact_ids = prune_campaign_facts(
                campaign,
                current_turn_index=current_turn_index,
            )
            if state_updated or pruned_fact_ids:
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
            selected_item_resolution = resolve_selected_stack_resolution(
                campaign,
                effective_actor_id,
                selected_stack_id=selected_stack_id,
                selected_item_id=selected_item_id,
            )
            selected_item = _resolve_selected_item_context(
                campaign,
                effective_actor_id,
                selected_item_resolution=selected_item_resolution,
                repo_root=self.repo.storage_root.parent,
            )
            selected_scene_target = _resolve_selected_scene_target_context(
                campaign,
                effective_actor_id,
                selected_target_id=selected_target_id,
            )
            selected_npc_memory_target = _selected_npc_memory_target(selected_scene_target)
            world = _resolve_world_context(self.repo, campaign.selected.world_id)
            movement_rules = _movement_rules_prompt_payload(
                campaign,
                effective_actor_id,
                world=world,
            )
            guidance = _build_guidance_prompt_payload(
                campaign,
                effective_actor_id,
                repo=self.repo,
                campaign_id=campaign_id,
                world=world,
                movement_rules=movement_rules,
            )
            fact_context = build_fact_prompt_context(
                campaign,
                effective_actor_id,
                current_turn_index=current_turn_index,
                selected_item_id=_selected_item_fact_id(
                    selected_item, selected_scene_target
                ),
                selected_scene_target_id=_selected_scene_target_fact_id(
                    selected_scene_target
                ),
            )
            npc_memory_context = build_npc_memory_context(
                campaign,
                npc_id=selected_npc_memory_target.get("id")
                if isinstance(selected_npc_memory_target, dict)
                else None,
                npc_label=selected_npc_memory_target.get("label")
                if isinstance(selected_npc_memory_target, dict)
                else None,
                current_turn_index=current_turn_index,
            )
            consequence_context = build_consequence_prompt_context(
                campaign,
                effective_actor_id,
                selected_scene_target=selected_scene_target,
            )
            turn_prompt = _load_turn_prompt(self.repo)
            turn_flow = _load_turn_flow(self.repo)
            system_prompt = _build_system_prompt(
                campaign,
                effective_actor_id,
                prompt_template=str(turn_prompt["text"]),
                world=world,
                movement_rules=movement_rules,
                guidance=guidance,
                selected_item=selected_item,
                selected_scene_target=selected_scene_target,
                fact_context=fact_context,
                npc_memory=npc_memory_context,
                consequence_context=consequence_context,
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
                    selected_item_resolution=selected_item_resolution,
                    selected_scene_target=selected_scene_target,
                    fact_context=build_fact_debug_context(
                        campaign,
                        effective_actor_id,
                        current_turn_index=current_turn_index,
                        selected_item_id=_selected_item_fact_id(
                            selected_item, selected_scene_target
                        ),
                        selected_scene_target_id=_selected_scene_target_fact_id(
                            selected_scene_target
                        ),
                    ),
                    npc_memory=build_npc_memory_debug_context(
                        campaign,
                        npc_id=selected_npc_memory_target.get("id")
                        if isinstance(selected_npc_memory_target, dict)
                        else None,
                        npc_label=selected_npc_memory_target.get("label")
                        if isinstance(selected_npc_memory_target, dict)
                        else None,
                        current_turn_index=current_turn_index,
                    ),
                    consequence_context=consequence_context,
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
                tool_calls = _apply_selected_scene_target_adapter(
                    campaign,
                    effective_actor_id,
                    tool_calls,
                    selected_scene_target=selected_scene_target,
                )
                tool_calls, suppressed_failed_calls = _suppress_repeated_illegal_requests(
                    self.repo,
                    campaign_id,
                    tool_calls,
                )
                state_before = _snapshot_state(campaign)
                applied_actions, tool_feedback = execute_tool_calls(
                    campaign,
                    effective_actor_id,
                    tool_calls,
                    repo=self.repo,
                    selected_stack_id=selected_stack_id,
                    selected_item_id=selected_item_id,
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
                npc_memory_written_fact_ids = _write_npc_memory_from_applied_actions(
                    campaign,
                    applied_actions,
                    effective_actor_id=effective_actor_id,
                    user_input=user_input,
                    turn_id=turn_id,
                    turn_number=turn_number,
                )
                mistake_record = _record_recoverable_failures(
                    campaign,
                    tool_calls,
                    applied_actions,
                    tool_feedback,
                    effective_actor_id=effective_actor_id,
                    turn_id=turn_id,
                    turn_number=turn_number,
                    world=world,
                )
                consequence_record = refresh_campaign_consequences(campaign)
                response_consequence_context = build_consequence_prompt_context(
                    campaign,
                    effective_actor_id,
                    selected_scene_target=selected_scene_target,
                )
                pruned_after_write_fact_ids = (
                    prune_campaign_facts(
                        campaign,
                        current_turn_index=turn_number,
                        keep_fact_ids=set(npc_memory_written_fact_ids),
                    )
                    if npc_memory_written_fact_ids
                    else []
                )
                milestone_changed = _advance_milestone(
                    campaign,
                    turn_number=turn_number,
                    retry_count=retry_count,
                )
                lifecycle_changed = _mark_ended_if_needed(campaign)

                if (
                    applied_actions
                    or milestone_changed
                    or lifecycle_changed
                    or npc_memory_written_fact_ids
                    or pruned_after_write_fact_ids
                    or mistake_record["recorded_signal_ids"]
                    or mistake_record["pruned_signal_ids"]
                    or consequence_record["triggered_consequence_ids"]
                    or consequence_record["removed_consequence_ids"]
                ):
                    self.repo.save_campaign(campaign)
                if response_debug is not None and npc_memory_written_fact_ids:
                    response_debug["npc_memory_written_fact_ids"] = list(
                        npc_memory_written_fact_ids
                    )
                if response_debug is not None and pruned_after_write_fact_ids:
                    response_debug["pruned_fact_ids_after_write"] = list(
                        pruned_after_write_fact_ids
                    )
                if response_debug is not None:
                    response_debug["mistakes"] = build_mistake_debug_context(
                        campaign,
                        recorded_signal_ids=mistake_record["recorded_signal_ids"],
                        pruned_signal_ids=mistake_record["pruned_signal_ids"],
                    )
                    response_debug["consequences"] = build_consequence_debug_context(
                        campaign,
                        prompt_context=response_consequence_context,
                        triggered_consequence_ids=consequence_record[
                            "triggered_consequence_ids"
                        ],
                        removed_consequence_ids=consequence_record[
                            "removed_consequence_ids"
                        ],
                        source_signal_ids=consequence_record["source_signal_ids"],
                    )

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
                entry.state_summary.inventory_stack_ids = _all_actor_inventory_stack_ids(
                    campaign
                )
                entry.state_summary.inventory_stacks = _all_actor_inventory_stacks(
                    campaign
                )
                entry.state_summary.objective = campaign.goal.text.strip()
                (
                    entry.state_summary.active_area_id,
                    entry.state_summary.active_area_name,
                    entry.state_summary.active_area_description,
                ) = _active_area_context(campaign, effective_actor_id)
                entry.state_summary.active_actor_inventory = _active_actor_inventory(
                    campaign, effective_actor_id
                )
                entry.state_summary.active_actor_inventory_stack_ids = (
                    _active_actor_inventory_stack_ids(campaign, effective_actor_id)
                )
                entry.state_summary.active_actor_inventory_stacks = (
                    _active_actor_inventory_stacks(campaign, effective_actor_id)
                )
                entry.state_summary.mistakes = build_mistake_state_summary(campaign)
                entry.state_summary.consequences = build_consequence_state_summary(
                    campaign
                )
                entry.state_summary.hostility = build_hostility_state_summary(campaign)
                self.repo.append_turn_log(campaign_id, entry)
                return _build_success_response(
                    entry,
                    tool_calls,
                    applied_actions,
                    tool_feedback,
                    campaign=campaign,
                    world=world,
                    effective_actor_id=effective_actor_id,
                    guidance=guidance,
                    user_input=user_input,
                    consequence_context=response_consequence_context,
                    triggered_consequence_ids=consequence_record[
                        "triggered_consequence_ids"
                    ],
                    debug_payload=response_debug,
                )
        finally:
            _CAMPAIGN_TURN_LOCKS.release(campaign_lock)


def _write_npc_memory_from_applied_actions(
    campaign: Campaign,
    applied_actions: List[AppliedAction],
    *,
    effective_actor_id: str,
    user_input: str,
    turn_id: str,
    turn_number: int,
) -> List[str]:
    written_fact_ids: List[str] = []
    for action in applied_actions:
        if not isinstance(action, AppliedAction) or action.tool != "scene_action":
            continue
        args = action.args if isinstance(action.args, dict) else {}
        if args.get("action") != "talk":
            continue
        result = action.result if isinstance(action.result, dict) else {}
        if result.get("ok") is False:
            continue
        target_id = args.get("target_id")
        if not isinstance(target_id, str) or not target_id.strip():
            continue
        target = campaign.entities.get(target_id.strip())
        if target is None or target.kind != "npc":
            continue
        fact = record_npc_memory_fact(
            campaign,
            actor_id=effective_actor_id,
            npc_id=target.id,
            npc_label=target.label,
            user_input=user_input,
            turn_id=turn_id,
            current_turn_index=turn_number,
        )
        if fact is not None:
            written_fact_ids.append(fact.fact_id)
    return written_fact_ids


def _record_recoverable_failures(
    campaign: Campaign,
    tool_calls: List[ToolCall],
    applied_actions: List[AppliedAction],
    tool_feedback: Optional[ToolFeedback],
    *,
    effective_actor_id: str,
    turn_id: str,
    turn_number: int,
    world: Optional[object],
) -> Dict[str, List[str]]:
    signals = _collect_recoverable_failure_signals(
        campaign,
        tool_calls,
        applied_actions,
        tool_feedback,
        effective_actor_id=effective_actor_id,
        world=world,
    )
    if not signals:
        return {"recorded_signal_ids": [], "pruned_signal_ids": []}
    return record_mistake_signals(
        campaign,
        signals,
        current_turn_index=turn_number,
        turn_id=turn_id,
    )


def _collect_recoverable_failure_signals(
    campaign: Campaign,
    tool_calls: List[ToolCall],
    applied_actions: List[AppliedAction],
    tool_feedback: Optional[ToolFeedback],
    *,
    effective_actor_id: str,
    world: Optional[object],
) -> List[CampaignMistakeSignalCreate]:
    tool_call_by_id = {
        call.id: call
        for call in tool_calls
        if isinstance(call, ToolCall) and isinstance(call.id, str) and call.id.strip()
    }
    signals: List[CampaignMistakeSignalCreate] = []
    failed_calls = (
        tool_feedback.failed_calls if isinstance(tool_feedback, ToolFeedback) else []
    )
    for failed_call in failed_calls:
        if not isinstance(failed_call, FailedCall):
            continue
        signal = _recoverable_failure_signal_from_failed_call(
            campaign,
            failed_call,
            tool_call_by_id,
            effective_actor_id=effective_actor_id,
            world=world,
        )
        if signal is not None:
            signals.append(signal)
    for action in applied_actions:
        if not isinstance(action, AppliedAction):
            continue
        signal = _recoverable_failure_signal_from_applied_action(
            campaign,
            action,
            effective_actor_id=effective_actor_id,
        )
        if signal is not None:
            signals.append(signal)
    return signals


def _recoverable_failure_signal_from_failed_call(
    campaign: Campaign,
    failed_call: FailedCall,
    tool_call_by_id: Dict[str, ToolCall],
    *,
    effective_actor_id: str,
    world: Optional[object],
) -> Optional[CampaignMistakeSignalCreate]:
    call = tool_call_by_id.get(failed_call.id)
    area_id, _, _ = _active_area_context(campaign, effective_actor_id)
    target_id = _mistake_target_id_for_tool_call(failed_call.tool, call)
    if failed_call.reason == "repeat_illegal_request":
        return CampaignMistakeSignalCreate(
            category="repeated_misuse",
            source_tool=failed_call.tool,
            reason=failed_call.reason,
            target_id=target_id,
            target_label=_mistake_target_label(campaign, target_id),
            area_id=area_id if isinstance(area_id, str) and area_id.strip() else None,
            metadata={"status": failed_call.status},
        )
    if failed_call.tool != "move":
        return None
    return _recoverable_failure_signal_from_failed_move(
        campaign,
        failed_call,
        call,
        effective_actor_id=effective_actor_id,
        world=world,
    )


def _recoverable_failure_signal_from_failed_move(
    campaign: Campaign,
    failed_call: FailedCall,
    call: Optional[ToolCall],
    *,
    effective_actor_id: str,
    world: Optional[object],
) -> Optional[CampaignMistakeSignalCreate]:
    reason = failed_call.reason.strip().lower()
    if reason not in {"missing_required_item", "invalid_args"}:
        return None
    from_area_id, _, _ = _active_area_context(campaign, effective_actor_id)
    to_area_id = _mistake_target_id_for_tool_call("move", call)
    if reason == "missing_required_item":
        required_item_id = None
        if (
            isinstance(from_area_id, str)
            and from_area_id.strip()
            and isinstance(to_area_id, str)
            and to_area_id.strip()
        ):
            required_item_id = _required_item_for_transition(
                campaign,
                from_area_id=from_area_id,
                to_area_id=to_area_id,
                world=world,
            )
        wrong_item = _actor_gate_item_hint(
            campaign,
            effective_actor_id,
            required_item_id=required_item_id,
        )
        metadata: Dict[str, object] = {}
        item_id = None
        if isinstance(wrong_item, dict):
            raw_item_id = wrong_item.get("item_id")
            if isinstance(raw_item_id, str) and raw_item_id.strip():
                item_id = raw_item_id.strip()
            wrong_item_label = wrong_item.get("label")
            if isinstance(wrong_item_label, str) and wrong_item_label.strip():
                metadata["item_label"] = wrong_item_label.strip()
        return CampaignMistakeSignalCreate(
            category="wrong_item" if isinstance(wrong_item, dict) else "blocked_attempt",
            source_tool="move",
            reason=reason,
            target_id=to_area_id,
            target_label=_mistake_target_label(campaign, to_area_id),
            area_id=from_area_id if isinstance(from_area_id, str) and from_area_id.strip() else None,
            item_id=item_id,
            required_item_id=required_item_id,
            metadata=metadata,
        )
    return CampaignMistakeSignalCreate(
        category="invalid_interaction",
        source_tool="move",
        reason=reason,
        target_id=to_area_id,
        target_label=_mistake_target_label(campaign, to_area_id),
        area_id=from_area_id if isinstance(from_area_id, str) and from_area_id.strip() else None,
        metadata={"status": failed_call.status},
    )


def _recoverable_failure_signal_from_applied_action(
    campaign: Campaign,
    action: AppliedAction,
    *,
    effective_actor_id: str,
) -> Optional[CampaignMistakeSignalCreate]:
    if action.tool != "scene_action":
        return None
    result = action.result if isinstance(action.result, dict) else {}
    if result.get("ok") is not False:
        return None
    error = result.get("error")
    if not isinstance(error, dict):
        return None
    error_code = error.get("code")
    if not isinstance(error_code, str) or not error_code.strip():
        return None
    category = _scene_action_failure_mistake_category(error_code)
    if category is None:
        return None
    area_id, _, _ = _active_area_context(campaign, effective_actor_id)
    target_id = _mistake_target_id_for_scene_action(action)
    action_name = action.args.get("action")
    normalized_action = (
        action_name.strip().lower()
        if isinstance(action_name, str) and action_name.strip()
        else "scene_action"
    )
    metadata: Dict[str, object] = {"error_code": error_code.strip().lower()}
    error_message = error.get("message")
    if isinstance(error_message, str) and error_message.strip():
        metadata["error_message"] = error_message.strip()
    return CampaignMistakeSignalCreate(
        category=category,
        source_tool="scene_action",
        reason=f"{normalized_action}:{error_code.strip().lower()}",
        target_id=target_id,
        target_label=_mistake_target_label(campaign, target_id),
        area_id=area_id if isinstance(area_id, str) and area_id.strip() else None,
        metadata=metadata,
    )


def _scene_action_failure_mistake_category(error_code: str) -> Optional[str]:
    normalized = error_code.strip().lower()
    if normalized in {"target_not_found", "invalid_args"}:
        return "invalid_interaction"
    if normalized in {
        "carry_limit",
        "locked",
        "missing_item",
        "not_allowed",
        "not_reachable",
    }:
        return "blocked_attempt"
    return None


def _mistake_target_id_for_tool_call(
    tool_name: str,
    call: Optional[ToolCall],
) -> Optional[str]:
    if not isinstance(call, ToolCall):
        return None
    if tool_name == "move":
        return _normalized_optional_string(call.args.get("to_area_id"))
    return _normalized_optional_string(call.args.get("target_id"))


def _mistake_target_id_for_scene_action(action: AppliedAction) -> Optional[str]:
    return _normalized_optional_string(action.args.get("target_id"))


def _mistake_target_label(campaign: Campaign, target_id: Optional[str]) -> Optional[str]:
    if not isinstance(target_id, str) or not target_id.strip():
        return None
    normalized_target_id = target_id.strip()
    area = campaign.map.areas.get(normalized_target_id)
    if area is not None and isinstance(area.name, str) and area.name.strip():
        return area.name.strip()
    entity = campaign.entities.get(normalized_target_id)
    if entity is not None and isinstance(entity.label, str) and entity.label.strip():
        return entity.label.strip()
    stack = campaign.items.get(normalized_target_id)
    if stack is not None and isinstance(stack.label, str) and stack.label.strip():
        return stack.label.strip()
    return _humanize_identifier(normalized_target_id)


def _normalized_optional_string(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


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


def _starter_items() -> Dict[str, object]:
    crate = create_runtime_item_stack(
        definition_id="crate_01",
        quantity=1,
        parent_type="area",
        parent_id="area_001",
        label="Old Crate",
        tags=["container", "wood"],
        verbs=["inspect", "open", "search", "take"],
        state={"locked": False, "opened": False},
        props={"mass": 12, "size": "medium"},
        stackable=False,
        is_container=True,
        stack_id_salt="starter:crate_01",
    )
    return {crate.stack_id: crate}


def _build_campaign_bootstrap(
    world_id: str,
    repo: Optional[FileRepo] = None,
) -> Dict[str, object]:
    world = repo.get_world(world_id) if repo is not None else None
    if world is None:
        world = build_world_preset(world_id)
    if world is not None:
        scenario_bootstrap = build_runtime_bootstrap_from_world(world)
        if scenario_bootstrap is not None:
            return {
                "start_area_id": scenario_bootstrap.start_area_id,
                "goal_text": scenario_bootstrap.goal_text,
                "map": scenario_bootstrap.map_data,
                "items": scenario_bootstrap.items,
                "entities": scenario_bootstrap.entities,
                "scenario_runtime_fragment": scenario_bootstrap.fragment,
            }
        if is_scenario_generator_world(world):
            raise ValueError(
                "scenario runtime bootstrap unavailable for world: "
                f"{world.world_id}"
            )
    preset = build_campaign_world_preset(world_id)
    if preset is not None:
        return {
            "start_area_id": preset.start_area_id,
            "goal_text": preset.goal_text,
            "map": preset.map_data,
            "items": preset.items,
            "entities": preset.entities,
            "scenario_runtime_fragment": None,
        }
    return {
        "start_area_id": "area_001",
        "goal_text": "Define the main objective",
        "map": _default_starter_map(),
        "items": _starter_items(),
        "entities": _starter_entities(),
        "scenario_runtime_fragment": None,
    }


def _ensure_minimum_state(
    campaign: Campaign,
    repo: Optional[FileRepo] = None,
) -> bool:
    updated = False
    if not isinstance(campaign.items, dict):
        campaign.items = {}
        updated = True
    if not isinstance(campaign.entities, dict):
        campaign.entities = {}
        updated = True
    if not campaign.map.areas:
        bootstrap = _build_campaign_bootstrap(campaign.selected.world_id, repo)
        campaign.map = bootstrap["map"]
        if not campaign.items:
            campaign.items = bootstrap["items"]
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
    if normalize_campaign_items(campaign):
        updated = True
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


def _normalize_scene_action_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    return normalized or ""


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
        "items": deepcopy(campaign.items),
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
    campaign.items = snapshot["items"]
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
    inventory_stacks = _all_actor_inventory_stacks(campaign)
    active_actor_inventory_stacks = _active_actor_inventory_stacks(campaign, resolved_actor_id)
    return {
        "positions": positions,
        "positions_parent": positions_parent,
        "positions_child": positions_child,
        "hp": hp,
        "character_states": character_states,
        "inventories": _all_actor_inventories(campaign),
        "inventory_stack_ids": _all_actor_inventory_stack_ids(campaign),
        "inventory_stacks": {
            actor_id: [stack_view.model_dump() for stack_view in stack_views]
            for actor_id, stack_views in inventory_stacks.items()
        },
        "objective": campaign.goal.text.strip(),
        "active_area_id": active_area_id,
        "active_area_name": active_area_name,
        "active_area_description": active_area_description,
        "active_actor_inventory": _active_actor_inventory(campaign, resolved_actor_id),
        "active_actor_inventory_stack_ids": _active_actor_inventory_stack_ids(
            campaign, resolved_actor_id
        ),
        "active_actor_inventory_stacks": [
            stack_view.model_dump() for stack_view in active_actor_inventory_stacks
        ],
        "hostility": build_hostility_state_summary(campaign),
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
    inventories = _all_actor_inventories(campaign)
    for actor_id in sorted(campaign.actors.keys()):
        actor = campaign.actors[actor_id]
        actor_meta = actor.meta if isinstance(actor.meta, dict) else {}
        meta_payload = _sanitize_actor_meta_for_prompt(actor_meta)
        actors_payload[actor_id] = {
            "position": actor.position,
            "hp": actor.hp,
            "character_state": actor.character_state,
            "inventory": inventories.get(actor_id, {}),
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
        "items_in_area": build_area_root_stack_views(campaign, area_id),
    }


_GATE_ITEM_HINT_KEYWORDS = ("key", "pass", "card", "slip", "seal", "badge", "permit")
_SELECTED_SCENE_TARGET_ACTIONS = {"inspect", "talk", "take", "use"}


def _humanize_identifier(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().replace("_", " ").replace("-", " ")
    normalized = " ".join(part for part in normalized.split() if part)
    return normalized.title()


def _resolve_world_context(repo: FileRepo, world_id: str):
    world = repo.get_world(world_id)
    if world is not None:
        return world
    return build_world_preset(world_id)


def _required_item_for_transition(
    campaign: Campaign,
    *,
    from_area_id: str,
    to_area_id: str,
    world: Optional[object],
) -> Optional[str]:
    fragment = campaign.scenario_runtime_fragment
    if fragment is not None:
        gate = fragment.gate
        if gate.from_area_id == from_area_id and gate.to_area_id == to_area_id:
            return gate.required_item_id
        return None
    required_item_id = required_item_for_move(
        campaign.selected.world_id, from_area_id, to_area_id
    )
    if not isinstance(required_item_id, str):
        return None
    normalized = required_item_id.strip()
    return normalized or None


def _area_prompt_label(campaign: Campaign, area_id: object) -> str:
    if isinstance(area_id, str):
        area = campaign.map.areas.get(area_id)
        if area is not None and isinstance(area.name, str) and area.name.strip():
            return area.name.strip()
        normalized = area_id.strip()
        if normalized:
            return _humanize_identifier(normalized)
    return "that area"


def _required_item_label(required_item_id: Optional[str]) -> str:
    if not isinstance(required_item_id, str) or not required_item_id.strip():
        return "the right item"
    return _humanize_identifier(required_item_id)


def _actor_gate_item_hint(
    campaign: Campaign,
    actor_id: str,
    *,
    required_item_id: Optional[str],
) -> Optional[Dict[str, str]]:
    for stack_view in build_actor_inventory_stack_views_from_items_only(campaign, actor_id):
        if hasattr(stack_view, "item_id"):
            item_id = getattr(stack_view, "item_id")
            label = getattr(stack_view, "label", "")
        elif isinstance(stack_view, dict):
            item_id = stack_view.get("item_id")
            label = stack_view.get("label")
        else:
            continue
        if isinstance(item_id, str) and item_id.strip() == required_item_id:
            continue
        candidate = (
            label.strip()
            if isinstance(label, str) and label.strip()
            else _humanize_identifier(item_id)
        )
        normalized = f"{candidate} {item_id}".lower()
        if any(keyword in normalized for keyword in _GATE_ITEM_HINT_KEYWORDS):
            return {
                "item_id": item_id.strip() if isinstance(item_id, str) else "",
                "label": candidate,
            }
    return None


def _actor_gate_item_label(
    campaign: Campaign,
    actor_id: str,
    *,
    required_item_id: Optional[str],
) -> Optional[str]:
    hint = _actor_gate_item_hint(
        campaign,
        actor_id,
        required_item_id=required_item_id,
    )
    if isinstance(hint, dict):
        label = hint.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return None


def _movement_rules_prompt_payload(
    campaign: Campaign,
    actor_id: str,
    *,
    world: Optional[object],
) -> Dict[str, object]:
    active_state = _CHARACTER_FACADE.get_state(campaign, actor_id)
    from_area_id = active_state.position if isinstance(active_state.position, str) else None
    payload: Dict[str, object] = {
        "current_area_id": from_area_id,
        "reachable_areas": [],
        "blocked_transitions": [],
    }
    if not isinstance(from_area_id, str) or not from_area_id.strip():
        return payload
    area = campaign.map.areas.get(from_area_id)
    if area is None:
        return payload

    reachable: List[Dict[str, str]] = []
    blocked: List[Dict[str, str]] = []
    for to_area_id in sorted(area.reachable_area_ids):
        target_name = _area_prompt_label(campaign, to_area_id)
        required_item_id = _required_item_for_transition(
            campaign,
            from_area_id=from_area_id,
            to_area_id=to_area_id,
            world=world,
        )
        if required_item_id is not None:
            quantity = get_actor_item_quantity_from_items_only(
                campaign,
                actor_id,
                required_item_id,
            )
            if quantity <= 0:
                blocked.append(
                    {
                        "to_area_id": to_area_id,
                        "name": target_name,
                        "reason": "locked",
                        "requires_item_id": required_item_id,
                        "requires_label": _required_item_label(required_item_id),
                    }
                )
                continue
        reachable.append({"to_area_id": to_area_id, "name": target_name})

    payload["reachable_areas"] = reachable
    payload["blocked_transitions"] = blocked
    return payload


def _interaction_rules_prompt_payload() -> Dict[str, object]:
    return {
        "take_requires_visible_target": True,
        "search_reveals_hidden_items": True,
        "blocked_moves_require_listed_item": True,
    }


def _normalized_text_list(values: object) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            continue
        value = raw.strip().lower()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _entity_area_id(entity: Entity) -> Optional[str]:
    if entity.loc.type != "area":
        return None
    area_id = entity.loc.id.strip() if isinstance(entity.loc.id, str) else ""
    return area_id or None


def _entity_primary_action(entity: Entity) -> str:
    verbs = _normalized_text_list(entity.verbs)
    if entity.kind == "npc" or "talk" in verbs:
        return "talk"
    if "search" in verbs:
        return "search"
    if "inspect" in verbs:
        return "inspect"
    if "open" in verbs:
        return "open"
    return "check"


def _entity_has_pending_item_source(entity: Entity, *, item_id: str) -> bool:
    state = entity.state if isinstance(entity.state, dict) else {}
    search_loot_definition_id = state.get("search_loot_definition_id")
    if (
        isinstance(search_loot_definition_id, str)
        and search_loot_definition_id.strip() == item_id
        and state.get("search_generated_loot") is not True
    ):
        return True
    inventory_item_id = state.get("inventory_item_id")
    if (
        isinstance(inventory_item_id, str)
        and inventory_item_id.strip() == item_id
        and state.get("inventory_granted") is not True
    ):
        return True
    return False


def _entity_has_pending_search_or_hint(entity: Entity) -> bool:
    state = entity.state if isinstance(entity.state, dict) else {}
    if "search" in _normalized_text_list(entity.verbs):
        if state.get("search_generated_loot") is not True:
            for key in (
                "search_loot_definition_id",
                "search_loot_stack_id",
                "search_loot_label",
                "inventory_item_id",
            ):
                value = state.get(key)
                if isinstance(value, str) and value.strip():
                    return True
    hint = state.get("hint")
    return isinstance(hint, str) and hint.strip() != ""


def _inventory_signature_from_mapping(mapping: Dict[str, int]) -> tuple[tuple[str, int], ...]:
    normalized: List[tuple[str, int]] = []
    for item_id in sorted(mapping.keys()):
        quantity = mapping[item_id]
        if isinstance(item_id, str) and isinstance(quantity, int):
            normalized.append((item_id, quantity))
    return tuple(normalized)


def _inventory_signature_from_state_summary(summary: Dict[str, object]) -> tuple[tuple[str, int], ...]:
    inventory = summary.get("active_actor_inventory")
    if not isinstance(inventory, dict):
        return tuple()
    normalized: Dict[str, int] = {}
    for item_id, quantity in inventory.items():
        if isinstance(item_id, str) and isinstance(quantity, int):
            normalized[item_id] = quantity
    return _inventory_signature_from_mapping(normalized)


def _collect_guidance_history(
    repo: FileRepo,
    campaign: Campaign,
    campaign_id: str,
    actor_id: str,
) -> Dict[str, object]:
    rows = repo.read_recent_turn_log_rows(campaign_id, limit=20)
    current_area_id, _, _ = _active_area_context(campaign, actor_id)
    current_inventory_signature = _inventory_signature_from_mapping(
        _active_actor_inventory(campaign, actor_id)
    )
    no_progress_streak = 0
    for row in rows:
        if not isinstance(row, dict):
            break
        summary = row.get("state_summary")
        if not isinstance(summary, dict):
            break
        row_area_id = summary.get("active_area_id")
        if (
            row_area_id == current_area_id
            and _inventory_signature_from_state_summary(summary)
            == current_inventory_signature
        ):
            no_progress_streak += 1
            continue
        break

    visited_area_ids: set[str] = set()
    if isinstance(current_area_id, str) and current_area_id.strip():
        visited_area_ids.add(current_area_id)
    talked_target_ids: set[str] = set()
    searched_target_ids: set[str] = set()
    blocked_move_failures = 0
    repeat_illegal_requests = 0
    blocked_failure_targets: Dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        summary = row.get("state_summary")
        if isinstance(summary, dict):
            area_id = summary.get("active_area_id")
            if isinstance(area_id, str) and area_id.strip():
                visited_area_ids.add(area_id.strip())
        applied_actions = row.get("applied_actions")
        if isinstance(applied_actions, list):
            for action in applied_actions:
                if not isinstance(action, dict) or action.get("tool") != "scene_action":
                    continue
                args = action.get("args")
                if not isinstance(args, dict):
                    continue
                target_id = args.get("target_id")
                if not isinstance(target_id, str) or not target_id.strip():
                    continue
                action_name = args.get("action")
                if action_name == "talk":
                    talked_target_ids.add(target_id.strip())
                if action_name == "search":
                    result = action.get("result")
                    if isinstance(result, dict) and result.get("ok") is not False:
                        searched_target_ids.add(target_id.strip())
        assistant_structured = row.get("assistant_structured")
        tool_calls = (
            assistant_structured.get("tool_calls")
            if isinstance(assistant_structured, dict)
            else None
        )
        tool_call_by_id: Dict[str, Dict[str, object]] = {}
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                tool_call_id = tool_call.get("id")
                if isinstance(tool_call_id, str) and tool_call_id.strip():
                    tool_call_by_id[tool_call_id.strip()] = tool_call
        tool_feedback = row.get("tool_feedback")
        failed_calls = (
            tool_feedback.get("failed_calls") if isinstance(tool_feedback, dict) else None
        )
        if not isinstance(failed_calls, list):
            continue
        for failed_call in failed_calls:
            if not isinstance(failed_call, dict):
                continue
            reason = failed_call.get("reason")
            if reason == "repeat_illegal_request":
                repeat_illegal_requests += 1
            if failed_call.get("tool") != "move" or reason != "missing_required_item":
                continue
            blocked_move_failures += 1
            failed_id = failed_call.get("id")
            if not isinstance(failed_id, str):
                continue
            tool_call = tool_call_by_id.get(failed_id.strip())
            if not isinstance(tool_call, dict):
                continue
            args = tool_call.get("args")
            if not isinstance(args, dict):
                continue
            to_area_id = args.get("to_area_id")
            if not isinstance(to_area_id, str) or not to_area_id.strip():
                continue
            blocked_failure_targets[to_area_id.strip()] = (
                blocked_failure_targets.get(to_area_id.strip(), 0) + 1
            )

    return {
        "visited_area_ids": sorted(visited_area_ids),
        "talked_target_ids": sorted(talked_target_ids),
        "searched_target_ids": sorted(searched_target_ids),
        "blocked_move_failures": blocked_move_failures,
        "blocked_failure_targets": blocked_failure_targets,
        "repeat_illegal_requests": repeat_illegal_requests,
        "no_progress_streak": no_progress_streak,
    }


def _guidance_hint_level(history: Dict[str, object]) -> int:
    blocked_move_failures = int(history.get("blocked_move_failures", 0) or 0)
    repeat_illegal_requests = int(history.get("repeat_illegal_requests", 0) or 0)
    no_progress_streak = int(history.get("no_progress_streak", 0) or 0)
    blocked_failure_targets = history.get("blocked_failure_targets")
    repeated_target_failures = 0
    if isinstance(blocked_failure_targets, dict):
        repeated_target_failures = max(
            (
                value
                for value in blocked_failure_targets.values()
                if isinstance(value, int)
            ),
            default=0,
        )
    level = 1
    if blocked_move_failures >= 1 or no_progress_streak >= 2:
        level = 2
    if repeat_illegal_requests > 0 or repeated_target_failures >= 2 or no_progress_streak >= 4:
        level = 3
    return max(1, min(level, 3))


def _guidance_area_priority(
    area_id: Optional[str],
    *,
    current_area_id: Optional[str],
    reachable_area_ids: set[str],
    visited_area_ids: set[str],
) -> int:
    if not isinstance(area_id, str) or not area_id.strip():
        return 99
    if area_id == current_area_id:
        return 0
    if area_id in reachable_area_ids and area_id not in visited_area_ids:
        return 1
    if area_id in reachable_area_ids:
        return 2
    if area_id not in visited_area_ids:
        return 3
    return 4


def _source_suggestion_text(
    *,
    area_name: str,
    source_label: str,
    action: str,
    hint_level: int,
) -> str:
    if hint_level <= 1:
        return f"{area_name} might be worth checking."
    if hint_level == 2:
        return f"{source_label} in {area_name} may be a useful lead."
    if action == "talk":
        return f"If you are stuck, {source_label} in {area_name} stands out as a useful lead."
    if action in {"search", "inspect", "open"}:
        return f"If you are stuck, {source_label} in {area_name} might be worth a closer look."
    return f"If you are stuck, {source_label} in {area_name} stands out as a possible lead."


def _route_suggestion_text(
    *,
    area_name: str,
    source_label: str,
    hint_level: int,
) -> str:
    if hint_level <= 1:
        return f"{area_name} may hold another lead."
    if hint_level == 2:
        return f"{source_label} in {area_name} might reveal another route."
    return f"If you are stuck, {source_label} in {area_name} stands out as a possible route lead."


def _area_suggestion_text(area_name: str, hint_level: int) -> str:
    if hint_level <= 1:
        return f"{area_name} might be worth checking."
    if hint_level == 2:
        return f"{area_name} may still be worth a closer look."
    return f"If you are stuck, {area_name} stands out right now."


def _dedupe_guidance_suggestions(
    suggestions: List[Dict[str, str]],
    *,
    max_count: int,
) -> List[Dict[str, str]]:
    deduped: List[Dict[str, str]] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        text = suggestion.get("text")
        if not isinstance(text, str):
            continue
        normalized = text.strip()
        if not normalized or normalized in seen:
            continue
        deduped.append({**suggestion, "text": normalized})
        seen.add(normalized)
        if len(deduped) >= max(1, max_count):
            break
    return deduped


def _blocked_transition_guidance(
    campaign: Campaign,
    *,
    actor_id: str,
    blocked_transition: Dict[str, str],
    hint_level: int,
    movement_rules: Dict[str, object],
    history: Dict[str, object],
) -> Dict[str, object]:
    current_area_id = movement_rules.get("current_area_id")
    reachable_area_ids = {
        entry.get("to_area_id")
        for entry in movement_rules.get("reachable_areas", [])
        if isinstance(entry, dict) and isinstance(entry.get("to_area_id"), str)
    }
    visited_area_ids = {
        area_id
        for area_id in history.get("visited_area_ids", [])
        if isinstance(area_id, str)
    }
    suggestions: List[Dict[str, str]] = []
    required_item_id = blocked_transition.get("requires_item_id")
    if isinstance(required_item_id, str) and required_item_id.strip():
        ranked_sources: List[tuple[int, str, str, str]] = []
        for entity in sorted(campaign.entities.values(), key=lambda item: item.id):
            area_id = _entity_area_id(entity)
            if area_id is None or not _entity_has_pending_item_source(
                entity, item_id=required_item_id.strip()
            ):
                continue
            area_name = _area_prompt_label(campaign, area_id)
            ranked_sources.append(
                (
                    _guidance_area_priority(
                        area_id,
                        current_area_id=current_area_id
                        if isinstance(current_area_id, str)
                        else None,
                        reachable_area_ids=reachable_area_ids,
                        visited_area_ids=visited_area_ids,
                    ),
                    area_name,
                    entity.label,
                    _entity_primary_action(entity),
                )
            )
        for _, area_name, source_label, action in sorted(ranked_sources):
            suggestions.append(
                {
                    "kind": "source",
                    "text": _source_suggestion_text(
                        area_name=area_name,
                        source_label=source_label,
                        action=action,
                        hint_level=hint_level,
                    ),
                }
            )
    ranked_routes: List[tuple[int, str, str]] = []
    for entity in sorted(campaign.entities.values(), key=lambda item: item.id):
        area_id = _entity_area_id(entity)
        if area_id is None:
            continue
        tags = {tag.strip().lower() for tag in entity.tags if isinstance(tag, str)}
        if not tags.intersection({"route_clue", "service_route"}):
            continue
        area_name = _area_prompt_label(campaign, area_id)
        ranked_routes.append(
            (
                _guidance_area_priority(
                    area_id,
                    current_area_id=current_area_id
                    if isinstance(current_area_id, str)
                    else None,
                    reachable_area_ids=reachable_area_ids,
                    visited_area_ids=visited_area_ids,
                ),
                area_name,
                entity.label,
            )
        )
    for _, area_name, source_label in sorted(ranked_routes):
        suggestions.append(
            {
                "kind": "route",
                "text": _route_suggestion_text(
                    area_name=area_name,
                    source_label=source_label,
                    hint_level=hint_level,
                ),
            }
        )
    return {
        "to_area_id": blocked_transition.get("to_area_id", ""),
        "name": blocked_transition.get("name", ""),
        "requires_label": blocked_transition.get("requires_label", ""),
        "suggestions": _dedupe_guidance_suggestions(
            suggestions,
            max_count=2 if hint_level >= 2 else 1,
        ),
    }


def _idle_guidance_suggestions(
    campaign: Campaign,
    *,
    actor_id: str,
    movement_rules: Dict[str, object],
    blocked_transition_hints: List[Dict[str, object]],
    history: Dict[str, object],
    hint_level: int,
) -> List[Dict[str, str]]:
    current_area_id = movement_rules.get("current_area_id")
    reachable_area_ids = {
        entry.get("to_area_id")
        for entry in movement_rules.get("reachable_areas", [])
        if isinstance(entry, dict) and isinstance(entry.get("to_area_id"), str)
    }
    talked_target_ids = {
        target_id
        for target_id in history.get("talked_target_ids", [])
        if isinstance(target_id, str)
    }
    searched_target_ids = {
        target_id
        for target_id in history.get("searched_target_ids", [])
        if isinstance(target_id, str)
    }
    suggestions: List[Dict[str, str]] = []
    for blocked_hint in blocked_transition_hints:
        blocked_suggestions = blocked_hint.get("suggestions")
        if isinstance(blocked_suggestions, list):
            suggestions.extend(
                item for item in blocked_suggestions if isinstance(item, dict)
            )
    local_candidates: List[tuple[int, str]] = []
    for entity in sorted(campaign.entities.values(), key=lambda item: item.id):
        area_id = _entity_area_id(entity)
        if area_id is None:
            continue
        action = _entity_primary_action(entity)
        if action == "talk" and entity.id in talked_target_ids:
            continue
        if action == "search" and entity.id in searched_target_ids:
            continue
        if action in {"talk", "search"} and not _entity_has_pending_search_or_hint(entity):
            continue
        priority = _guidance_area_priority(
            area_id,
            current_area_id=current_area_id if isinstance(current_area_id, str) else None,
            reachable_area_ids=reachable_area_ids,
            visited_area_ids={
                area for area in history.get("visited_area_ids", []) if isinstance(area, str)
            },
        )
        if priority > 2:
            continue
        area_name = _area_prompt_label(campaign, area_id)
        local_candidates.append(
            (
                priority,
                _source_suggestion_text(
                    area_name=area_name,
                    source_label=entity.label,
                    action=action,
                    hint_level=2 if area_id == current_area_id else min(hint_level, 2),
                ),
            )
        )
    for _, text in sorted(local_candidates):
        suggestions.append({"kind": "local", "text": text})
    for reachable_area_id in sorted(reachable_area_ids):
        area_name = _area_prompt_label(campaign, reachable_area_id)
        suggestions.append({"kind": "area", "text": _area_suggestion_text(area_name, hint_level)})
    return _dedupe_guidance_suggestions(suggestions, max_count=2)


def _item_relevance_suggestions(
    campaign: Campaign,
    *,
    actor_id: str,
    world: Optional[object],
) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []
    seen_item_ids: set[str] = set()
    for stack_view in build_actor_inventory_stack_views_from_items_only(campaign, actor_id):
        item_id = getattr(stack_view, "item_id", None)
        label = getattr(stack_view, "label", "")
        if not isinstance(item_id, str) or not item_id.strip() or item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        for from_area_id, area in sorted(campaign.map.areas.items()):
            for to_area_id in sorted(area.reachable_area_ids):
                required_item_id = _required_item_for_transition(
                    campaign,
                    from_area_id=from_area_id,
                    to_area_id=to_area_id,
                    world=world,
                )
                if required_item_id != item_id:
                    continue
                target_name = _area_prompt_label(campaign, to_area_id)
                item_label = label.strip() if isinstance(label, str) and label.strip() else _humanize_identifier(item_id)
                suggestions.append(
                    {
                        "item_id": item_id,
                        "label": item_label,
                        "text": f"{item_label} may be more relevant around {target_name}.",
                    }
                )
                break
    return _dedupe_guidance_suggestions(suggestions, max_count=3)


def _build_guidance_prompt_payload(
    campaign: Campaign,
    actor_id: str,
    *,
    repo: FileRepo,
    campaign_id: str,
    world: Optional[object],
    movement_rules: Dict[str, object],
) -> Dict[str, object]:
    history = _collect_guidance_history(repo, campaign, campaign_id, actor_id)
    hint_level = _guidance_hint_level(history)
    blocked_transition_hints: List[Dict[str, object]] = []
    for blocked_transition in movement_rules.get("blocked_transitions", []):
        if not isinstance(blocked_transition, dict):
            continue
        blocked_transition_hints.append(
            _blocked_transition_guidance(
                campaign,
                actor_id=actor_id,
                blocked_transition=blocked_transition,
                hint_level=hint_level,
                movement_rules=movement_rules,
                history=history,
            )
        )
    return {
        "hint_level": hint_level,
        "recent_signals": {
            "blocked_move_failures": int(history.get("blocked_move_failures", 0) or 0),
            "no_progress_streak": int(history.get("no_progress_streak", 0) or 0),
            "repeat_illegal_requests": int(history.get("repeat_illegal_requests", 0) or 0),
        },
        "blocked_transition_hints": blocked_transition_hints,
        "idle_suggestions": _idle_guidance_suggestions(
            campaign,
            actor_id=actor_id,
            movement_rules=movement_rules,
            blocked_transition_hints=blocked_transition_hints,
            history=history,
            hint_level=hint_level,
        ),
        "item_relevance": _item_relevance_suggestions(
            campaign,
            actor_id=actor_id,
            world=world,
        ),
    }


def _guidance_hint_level_value(guidance: Optional[Dict[str, object]]) -> int:
    if not isinstance(guidance, dict):
        return 1
    value = guidance.get("hint_level")
    if not isinstance(value, int):
        return 1
    return max(1, min(value, 3))


def _blocked_guidance_texts_for_area(
    guidance: Optional[Dict[str, object]],
    *,
    to_area_id: object,
    max_count: int,
) -> List[str]:
    if not isinstance(guidance, dict) or not isinstance(to_area_id, str):
        return []
    blocked_transition_hints = guidance.get("blocked_transition_hints")
    if not isinstance(blocked_transition_hints, list):
        return []
    for blocked_hint in blocked_transition_hints:
        if not isinstance(blocked_hint, dict):
            continue
        if blocked_hint.get("to_area_id") != to_area_id:
            continue
        suggestions = blocked_hint.get("suggestions")
        if not isinstance(suggestions, list):
            return []
        texts: List[str] = []
        seen: set[str] = set()
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            text = suggestion.get("text")
            if not isinstance(text, str):
                continue
            normalized = text.strip()
            if not normalized or normalized in seen:
                continue
            texts.append(normalized)
            seen.add(normalized)
            if len(texts) >= max(1, max_count):
                break
        return texts
    return []


def _item_relevance_text_for_item(
    guidance: Optional[Dict[str, object]],
    *,
    item_id: Optional[str],
    item_label: Optional[str],
) -> Optional[str]:
    if not isinstance(guidance, dict):
        return None
    item_relevance = guidance.get("item_relevance")
    if not isinstance(item_relevance, list):
        return None
    normalized_item_id = item_id.strip().lower() if isinstance(item_id, str) else ""
    normalized_item_label = item_label.strip().lower() if isinstance(item_label, str) else ""
    for suggestion in item_relevance:
        if not isinstance(suggestion, dict):
            continue
        candidate_id = suggestion.get("item_id")
        candidate_label = suggestion.get("label")
        text = suggestion.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        if isinstance(candidate_id, str) and candidate_id.strip().lower() == normalized_item_id:
            return text.strip()
        if (
            normalized_item_label
            and isinstance(candidate_label, str)
            and candidate_label.strip().lower() == normalized_item_label
        ):
            return text.strip()
    return None


def _combine_guidance_sentences(parts: List[object]) -> str:
    normalized_parts: List[str] = []
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, str):
            continue
        text = part.strip()
        if not text or text in seen:
            continue
        normalized_parts.append(text)
        seen.add(text)
    return " ".join(normalized_parts)


def _looks_like_idle_guidance_request(user_input: object) -> bool:
    if not isinstance(user_input, str):
        return False
    lowered = " ".join(user_input.strip().lower().split())
    if not lowered:
        return False
    guidance_phrases = (
        "what now",
        "what should i do",
        "what do i do",
        "where should i go",
        "where do i go",
        "what next",
        "next step",
        "any idea",
        "i'm stuck",
        "im stuck",
        "help me progress",
        "help",
    )
    return any(phrase in lowered for phrase in guidance_phrases)


def _build_system_prompt(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    prompt_template: str,
    world: Optional[object] = None,
    movement_rules: Optional[Dict[str, object]] = None,
    guidance: Optional[Dict[str, object]] = None,
    selected_item: Optional[Dict[str, object]] = None,
    selected_scene_target: Optional[Dict[str, object]] = None,
    fact_context: Optional[Dict[str, object]] = None,
    npc_memory: Optional[Dict[str, object]] = None,
    consequence_context: Optional[Dict[str, object]] = None,
) -> str:
    positions, _, _, hp, character_states = _derive_character_state_maps(campaign)
    actors_payload, adopted_profiles_by_actor = _build_actor_prompt_payloads(campaign)
    compress_enabled = campaign.settings_snapshot.context.compress_enabled
    if movement_rules is None:
        movement_rules = _movement_rules_prompt_payload(
            campaign,
            effective_actor_id,
            world=world,
        )
    reachable_area_ids = [
        entry["to_area_id"]
        for entry in movement_rules.get("reachable_areas", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("to_area_id"), str)
        and entry.get("to_area_id").strip()
    ]
    guidance_payload = guidance if isinstance(guidance, dict) else {}
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
                "reachable_from_active": reachable_area_ids,
            },
            "positions": positions,
            "hp": hp,
            "character_states": character_states,
            "active_actor_inventory": _active_actor_inventory(
                campaign, effective_actor_id
            ),
            "scene": _scene_prompt_payload(campaign, effective_actor_id),
            "movement_rules": movement_rules,
            "guidance": guidance_payload,
            "interaction_rules": _interaction_rules_prompt_payload(),
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
            "movement_rules": movement_rules,
            "guidance": guidance_payload,
            "interaction_rules": _interaction_rules_prompt_payload(),
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
    if selected_scene_target:
        payload["selected_scene_target"] = dict(selected_scene_target)
    if fact_context:
        payload["fact_context"] = dict(fact_context)
    if npc_memory:
        payload["npc_memory"] = dict(npc_memory)
    if consequence_context:
        payload["consequences"] = dict(consequence_context)
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
    selected_item_resolution: Optional[SelectedStackResolution] = None,
    selected_scene_target: Optional[Dict[str, object]] = None,
    fact_context: Optional[Dict[str, object]] = None,
    npc_memory: Optional[Dict[str, object]] = None,
    consequence_context: Optional[Dict[str, object]] = None,
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
    selected_item_resolution_debug = _build_selected_item_resolution_debug(
        campaign,
        active_actor_id,
        selected_item_resolution,
    )
    if selected_item_resolution_debug is not None:
        payload["selected_item_resolution"] = selected_item_resolution_debug
    selected_scene_target_debug = _build_selected_scene_target_debug(
        selected_scene_target
    )
    if selected_scene_target_debug is not None:
        payload["selected_scene_target"] = selected_scene_target_debug
    if isinstance(fact_context, dict):
        payload["fact_context"] = dict(fact_context)
    if isinstance(npc_memory, dict):
        payload["npc_memory"] = dict(npc_memory)
    if isinstance(consequence_context, dict):
        payload["consequence_context"] = dict(consequence_context)
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


def _build_selected_item_resolution_debug(
    campaign: Campaign,
    active_actor_id: str,
    selected_item_resolution: Optional[SelectedStackResolution],
) -> Optional[Dict[str, object]]:
    if not isinstance(selected_item_resolution, SelectedStackResolution):
        return None
    payload: Dict[str, object] = {
        "requested_item_id": selected_item_resolution.requested_item_id,
        "requested_stack_id": selected_item_resolution.requested_stack_id,
        "resolved_item_id": selected_item_resolution.resolved_item_id,
        "resolved_stack_id": selected_item_resolution.resolved_stack_id,
        "status": selected_item_resolution.status,
        "reason": selected_item_resolution.reason,
    }
    resolved_stack = selected_item_resolution.resolved_stack
    if resolved_stack is None:
        return payload
    if isinstance(resolved_stack.label, str) and resolved_stack.label.strip():
        payload["label"] = resolved_stack.label.strip()
    if isinstance(resolved_stack.quantity, int) and resolved_stack.quantity > 0:
        payload["stack_quantity"] = resolved_stack.quantity
    total_quantity = get_actor_item_quantity_from_items_only(
        campaign,
        active_actor_id,
        selected_item_resolution.resolved_item_id,
    )
    if total_quantity > 0:
        payload["total_quantity"] = total_quantity
    return payload


def _build_selected_scene_target_debug(
    selected_scene_target: Optional[Dict[str, object]],
) -> Optional[Dict[str, object]]:
    if not isinstance(selected_scene_target, dict):
        return None
    target_id = selected_scene_target.get("id")
    if not isinstance(target_id, str) or not target_id.strip():
        return None
    payload: Dict[str, object] = {"id": target_id.strip()}
    for key in ("kind", "label", "source", "item_id"):
        value = selected_scene_target.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    return payload


def _scene_target_view_supports_action(
    action: str,
    *,
    kind: str,
    verbs: object,
) -> bool:
    normalized_action = _normalize_scene_action_name(action)
    if normalized_action not in _SELECTED_SCENE_TARGET_ACTIONS:
        return False
    normalized_verbs = (
        {
            verb.strip().lower()
            for verb in verbs
            if isinstance(verb, str) and verb.strip()
        }
        if isinstance(verbs, list)
        else set()
    )
    if normalized_action == "talk":
        return kind == "npc" or "talk" in normalized_verbs
    return normalized_action in normalized_verbs


def _selected_scene_target_supports_action(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    target_id: str,
    action: str,
) -> bool:
    normalized_target_id = target_id.strip() if isinstance(target_id, str) else ""
    if not normalized_target_id:
        return False
    area_id, _, _ = _active_area_context(campaign, effective_actor_id)
    if not isinstance(area_id, str) or not area_id.strip():
        return False

    for stack_view in build_area_root_stack_views(campaign, area_id):
        candidate_id = stack_view.get("id")
        if not isinstance(candidate_id, str) or candidate_id.strip() != normalized_target_id:
            continue
        return _scene_target_view_supports_action(
            action,
            kind="item",
            verbs=stack_view.get("verbs"),
        )

    for entity_view in build_area_local_entity_views(campaign, area_id):
        candidate_id = entity_view.get("id")
        if not isinstance(candidate_id, str) or candidate_id.strip() != normalized_target_id:
            continue
        kind = entity_view.get("kind")
        normalized_kind = kind.strip() if isinstance(kind, str) and kind.strip() else ""
        return _scene_target_view_supports_action(
            action,
            kind=normalized_kind,
            verbs=entity_view.get("verbs"),
        )

    return False


def _apply_selected_scene_target_adapter(
    campaign: Campaign,
    effective_actor_id: str,
    tool_calls: List[ToolCall],
    *,
    selected_scene_target: Optional[Dict[str, object]],
) -> List[ToolCall]:
    if not isinstance(selected_scene_target, dict):
        return tool_calls
    target_id = selected_scene_target.get("id")
    if not isinstance(target_id, str) or not target_id.strip():
        return tool_calls
    normalized_target_id = target_id.strip()
    adapted: List[ToolCall] = []
    for call in tool_calls:
        if not isinstance(call, ToolCall) or call.tool != "scene_action":
            adapted.append(call)
            continue
        action = _normalize_scene_action_name(call.args.get("action"))
        if action not in _SELECTED_SCENE_TARGET_ACTIONS:
            adapted.append(call)
            continue
        if not _selected_scene_target_supports_action(
            campaign,
            effective_actor_id,
            target_id=normalized_target_id,
            action=action,
        ):
            adapted.append(call)
            continue
        current_target_id = call.args.get("target_id")
        if isinstance(current_target_id, str) and current_target_id.strip() == normalized_target_id:
            adapted.append(call)
            continue
        adapted.append(
            ToolCall(
                id=call.id,
                tool=call.tool,
                args={**call.args, "target_id": normalized_target_id},
                reason=call.reason,
            )
        )
    return adapted


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
    campaign: Campaign,
    world: Optional[object],
    effective_actor_id: str,
    guidance: Optional[Dict[str, object]] = None,
    user_input: Optional[str] = None,
    consequence_context: Optional[Dict[str, object]] = None,
    triggered_consequence_ids: Optional[List[str]] = None,
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
    _apply_failure_tool_narrative_fallback(
        response,
        campaign,
        effective_actor_id,
        tool_calls,
        world=world,
        guidance=guidance,
    )
    _apply_guidance_narrative_fallback(
        response,
        user_input=user_input,
        guidance=guidance,
    )
    _apply_consequence_narrative_fallback(
        response,
        consequence_context=consequence_context,
        triggered_consequence_ids=triggered_consequence_ids,
    )
    if debug_payload:
        response["debug"] = dict(debug_payload)
    return response


def _applied_action_failed(item: object) -> bool:
    result: Optional[Dict[str, object]] = None
    if isinstance(item, AppliedAction):
        result = item.result
    elif isinstance(item, dict):
        candidate = item.get("result")
        if isinstance(candidate, dict):
            result = candidate
    if not isinstance(result, dict):
        return False
    return result.get("ok") is False


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
    failed_scene_action = any(_applied_action_failed(item) for item in applied_actions)
    successful_actions = any(not _applied_action_failed(item) for item in applied_actions)
    if failed_scene_action and not successful_actions:
        return ""
    if failed_calls and not applied_actions:
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


def _apply_failure_tool_narrative_fallback(
    response: Dict[str, object],
    campaign: Campaign,
    effective_actor_id: str,
    tool_calls: List[ToolCall],
    *,
    world: Optional[object],
    guidance: Optional[Dict[str, object]] = None,
) -> None:
    if not isinstance(response, dict):
        return
    narrative_text = response.get("narrative_text")
    if isinstance(narrative_text, str) and narrative_text.strip():
        return
    tool_feedback = response.get("tool_feedback")
    if not isinstance(tool_feedback, dict):
        return
    failed_calls = tool_feedback.get("failed_calls")
    if not isinstance(failed_calls, list) or not failed_calls:
        return
    tool_call_by_id = {
        call.id: call
        for call in tool_calls
        if isinstance(call, ToolCall) and isinstance(call.id, str)
    }
    for failed_call in failed_calls:
        if not isinstance(failed_call, dict):
            continue
        message = _build_failed_call_narrative(
            campaign,
            effective_actor_id,
            failed_call,
            tool_call_by_id,
            world=world,
            guidance=guidance,
        )
        if isinstance(message, str) and message.strip():
            response["narrative_text"] = message.strip()
            return


def _build_failed_call_narrative(
    campaign: Campaign,
    effective_actor_id: str,
    failed_call: Dict[str, object],
    tool_call_by_id: Dict[str, ToolCall],
    *,
    world: Optional[object],
    guidance: Optional[Dict[str, object]] = None,
) -> Optional[str]:
    failed_id = failed_call.get("id")
    if not isinstance(failed_id, str):
        return None
    tool_name = failed_call.get("tool")
    if tool_name != "move":
        return None
    reason = failed_call.get("reason")
    call = tool_call_by_id.get(failed_id)
    return _build_failed_move_narrative(
        campaign,
        effective_actor_id,
        call,
        reason=reason if isinstance(reason, str) else "",
        world=world,
        guidance=guidance,
    )


def _build_failed_move_narrative(
    campaign: Campaign,
    effective_actor_id: str,
    call: Optional[ToolCall],
    *,
    reason: str,
    world: Optional[object],
    guidance: Optional[Dict[str, object]] = None,
) -> str:
    from_area_id, from_area_name, _ = _active_area_context(campaign, effective_actor_id)
    if call is None:
        return "That move does not work from here."
    to_area_id = call.args.get("to_area_id")
    target_name = _area_prompt_label(campaign, to_area_id)

    if reason == "missing_required_item" and isinstance(from_area_id, str):
        required_item_id = _required_item_for_transition(
            campaign,
            from_area_id=from_area_id,
            to_area_id=to_area_id if isinstance(to_area_id, str) else "",
            world=world,
        )
        required_label = _required_item_label(required_item_id)
        wrong_item = _actor_gate_item_hint(
            campaign,
            effective_actor_id,
            required_item_id=required_item_id,
        )
        hint_level = _guidance_hint_level_value(guidance)
        blocked_suggestions = _blocked_guidance_texts_for_area(
            guidance,
            to_area_id=to_area_id,
            max_count=2 if hint_level >= 2 else 1,
        )
        parts: List[object] = []
        follow_up_hints: List[str] = []
        if isinstance(wrong_item, dict):
            wrong_item_label = wrong_item.get("label")
            if isinstance(wrong_item_label, str) and wrong_item_label.strip():
                parts.append(
                    f"The way to {target_name} is locked. "
                    f"{wrong_item_label.strip()} does not work here. You may need {required_label}."
                )
                item_relevance_text = _item_relevance_text_for_item(
                    guidance,
                    item_id=wrong_item.get("item_id")
                    if isinstance(wrong_item.get("item_id"), str)
                    else None,
                    item_label=wrong_item_label,
                )
                if item_relevance_text:
                    follow_up_hints.append(item_relevance_text)
            else:
                parts.append(f"The way to {target_name} is locked. You may need {required_label}.")
        else:
            parts.append(f"The way to {target_name} is locked. You may need {required_label}.")
        for text in blocked_suggestions:
            if not isinstance(text, str) or not text.strip():
                continue
            follow_up_hints.append(text.strip())
        parts.extend(follow_up_hints[:2])
        return _combine_guidance_sentences(parts)

    if reason in {"invalid_args", "repeat_illegal_request"}:
        if isinstance(to_area_id, str) and isinstance(from_area_id, str):
            if to_area_id == from_area_id:
                return f"You are already in {from_area_name or target_name}."
            source_area = campaign.map.areas.get(from_area_id)
            if source_area is None or to_area_id not in source_area.reachable_area_ids:
                return f"You cannot reach {target_name} directly from here."
        return "You cannot move there from your current position."

    return "That move does not work from here."


def _apply_guidance_narrative_fallback(
    response: Dict[str, object],
    *,
    user_input: Optional[str],
    guidance: Optional[Dict[str, object]],
) -> None:
    if not isinstance(response, dict):
        return
    narrative_text = response.get("narrative_text")
    if isinstance(narrative_text, str) and narrative_text.strip():
        return
    if response.get("tool_feedback") is not None:
        return
    applied_actions = response.get("applied_actions")
    if isinstance(applied_actions, list) and applied_actions:
        return
    if not _looks_like_idle_guidance_request(user_input):
        return
    if not isinstance(guidance, dict):
        return
    idle_suggestions = guidance.get("idle_suggestions")
    if not isinstance(idle_suggestions, list):
        return
    suggestions: List[str] = []
    seen: set[str] = set()
    for suggestion in idle_suggestions:
        if not isinstance(suggestion, dict):
            continue
        text = suggestion.get("text")
        if not isinstance(text, str):
            continue
        normalized = text.strip()
        if not normalized or normalized in seen:
            continue
        suggestions.append(normalized)
        seen.add(normalized)
        if len(suggestions) >= 2:
            break
    if not suggestions:
        return
    if len(suggestions) == 1:
        response["narrative_text"] = suggestions[0]
        return
    response["narrative_text"] = f"{suggestions[0]} {suggestions[1]}"


def _apply_consequence_narrative_fallback(
    response: Dict[str, object],
    *,
    consequence_context: Optional[Dict[str, object]],
    triggered_consequence_ids: Optional[List[str]],
) -> None:
    if not isinstance(response, dict):
        return
    if not isinstance(consequence_context, dict):
        return
    triggered = set(triggered_consequence_ids or [])
    if not triggered:
        return
    items = consequence_context.get("items")
    if not isinstance(items, list):
        return
    hint = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        consequence_id = item.get("consequence_id")
        if not isinstance(consequence_id, str) or consequence_id not in triggered:
            continue
        narrative_hint = item.get("narrative_hint")
        if isinstance(narrative_hint, str) and narrative_hint.strip():
            hint = narrative_hint.strip()
            break
    if not hint:
        return
    current = response.get("narrative_text")
    if not isinstance(current, str) or not current.strip():
        response["narrative_text"] = hint
        return
    if hint.lower() in current.lower():
        return
    response["narrative_text"] = f"{current.strip()} {hint}"


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
    state_summary.inventory_stack_ids = _all_actor_inventory_stack_ids(campaign)
    state_summary.inventory_stacks = _all_actor_inventory_stacks(campaign)
    state_summary.objective = campaign.goal.text.strip()
    (
        state_summary.active_area_id,
        state_summary.active_area_name,
        state_summary.active_area_description,
    ) = _active_area_context(campaign, effective_actor_id)
    state_summary.active_actor_inventory = _active_actor_inventory(
        campaign, effective_actor_id
    )
    state_summary.active_actor_inventory_stack_ids = _active_actor_inventory_stack_ids(
        campaign, effective_actor_id
    )
    state_summary.active_actor_inventory_stacks = _active_actor_inventory_stacks(
        campaign, effective_actor_id
    )
    state_summary.mistakes = build_mistake_state_summary(campaign)
    state_summary.consequences = build_consequence_state_summary(campaign)
    state_summary.hostility = build_hostility_state_summary(campaign)
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
    return derive_actor_inventory_from_items_only(campaign, actor_id)


def _active_actor_inventory_stack_ids(
    campaign: Campaign, actor_id: str
) -> Dict[str, List[str]]:
    return derive_actor_inventory_stack_ids_from_items_only(campaign, actor_id)


def _resolve_selected_item_context(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    selected_item_resolution: SelectedStackResolution,
    repo_root: Path,
) -> Optional[Dict[str, object]]:
    selected_stack = selected_item_resolution.resolved_stack
    if selected_stack is None:
        return None
    quantity = get_actor_item_quantity_from_items_only(
        campaign, effective_actor_id, selected_stack.definition_id
    )
    if quantity <= 0:
        return None
    selected_item = {
        "id": selected_stack.definition_id,
        "stack_id": selected_stack.stack_id,
        "quantity": quantity,
        "stack_quantity": selected_stack.quantity,
    }
    label = selected_stack.label.strip()
    if label:
        selected_item["label"] = label
    item_metadata = load_item_catalog(repo_root).get(selected_stack.definition_id, {})
    if isinstance(item_metadata, dict):
        name = item_metadata.get("name")
        description = item_metadata.get("description")
        if isinstance(name, str) and name.strip():
            selected_item["name"] = name.strip()
        if isinstance(description, str) and description.strip():
            selected_item["description"] = description.strip()
    return selected_item


def _selected_item_fact_id(
    selected_item: Optional[Dict[str, object]],
    selected_scene_target: Optional[Dict[str, object]],
) -> Optional[str]:
    if isinstance(selected_item, dict):
        item_id = selected_item.get("id")
        if isinstance(item_id, str) and item_id.strip():
            return item_id.strip()
    if not isinstance(selected_scene_target, dict):
        return None
    target_kind = selected_scene_target.get("kind")
    if not isinstance(target_kind, str) or target_kind.strip() != "item":
        return None
    item_id = selected_scene_target.get("item_id")
    if isinstance(item_id, str) and item_id.strip():
        return item_id.strip()
    return None


def _selected_scene_target_fact_id(
    selected_scene_target: Optional[Dict[str, object]],
) -> Optional[str]:
    if not isinstance(selected_scene_target, dict):
        return None
    target_kind = selected_scene_target.get("kind")
    if not isinstance(target_kind, str) or target_kind.strip() == "item":
        return None
    target_id = selected_scene_target.get("id")
    if isinstance(target_id, str) and target_id.strip():
        return target_id.strip()
    return None


def _selected_npc_memory_target(
    selected_scene_target: Optional[Dict[str, object]],
) -> Optional[Dict[str, str]]:
    if not isinstance(selected_scene_target, dict):
        return None
    target_kind = selected_scene_target.get("kind")
    if not isinstance(target_kind, str) or target_kind.strip() != "npc":
        return None
    target_id = selected_scene_target.get("id")
    if not isinstance(target_id, str) or not target_id.strip():
        return None
    payload = {"id": target_id.strip()}
    label = selected_scene_target.get("label")
    if isinstance(label, str) and label.strip():
        payload["label"] = label.strip()
    return payload


def _resolve_selected_scene_target_context(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    selected_target_id: Optional[str],
) -> Optional[Dict[str, object]]:
    if not isinstance(selected_target_id, str):
        return None
    normalized_target_id = selected_target_id.strip()
    if not normalized_target_id:
        return None
    area_id, _, _ = _active_area_context(campaign, effective_actor_id)
    if not isinstance(area_id, str) or not area_id.strip():
        raise ValueError("selected_target_id requires an active area")

    for stack_view in build_area_root_stack_views(campaign, area_id):
        candidate_id = stack_view.get("id")
        if not isinstance(candidate_id, str) or candidate_id.strip() != normalized_target_id:
            continue
        if not any(
            _scene_target_view_supports_action(
                action,
                kind="item",
                verbs=stack_view.get("verbs"),
            )
            for action in _SELECTED_SCENE_TARGET_ACTIONS
        ):
            break
        payload: Dict[str, object] = {
            "id": candidate_id.strip(),
            "kind": "item",
            "source": "area_stack",
        }
        label = stack_view.get("label")
        if isinstance(label, str) and label.strip():
            payload["label"] = label.strip()
        item_id = stack_view.get("item_id")
        if isinstance(item_id, str) and item_id.strip():
            payload["item_id"] = item_id.strip()
        return payload

    for entity_view in build_area_local_entity_views(campaign, area_id):
        candidate_id = entity_view.get("id")
        if not isinstance(candidate_id, str) or candidate_id.strip() != normalized_target_id:
            continue
        kind = entity_view.get("kind")
        normalized_kind = kind.strip() if isinstance(kind, str) and kind.strip() else ""
        if not any(
            _scene_target_view_supports_action(
                action,
                kind=normalized_kind,
                verbs=entity_view.get("verbs"),
            )
            for action in _SELECTED_SCENE_TARGET_ACTIONS
        ):
            break
        payload = {
            "id": candidate_id.strip(),
            "kind": normalized_kind,
            "source": "entity",
        }
        label = entity_view.get("label")
        if isinstance(label, str) and label.strip():
            payload["label"] = label.strip()
        return payload

    raise ValueError(
        f"selected_target_id is not interactable in the current area: {normalized_target_id}"
    )


def _all_actor_inventories(campaign: Campaign) -> Dict[str, Dict[str, int]]:
    return derive_all_actor_inventories_from_items_only(campaign)


def _all_actor_inventory_stack_ids(campaign: Campaign) -> Dict[str, Dict[str, List[str]]]:
    return derive_all_actor_inventory_stack_ids_from_items_only(campaign)


def _active_actor_inventory_stacks(campaign: Campaign, actor_id: str):
    return build_actor_inventory_stack_views_from_items_only(campaign, actor_id)


def _all_actor_inventory_stacks(campaign: Campaign):
    return build_all_actor_inventory_stack_views_from_items_only(campaign)


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
