from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set

from backend.domain.mistake_models import (
    CampaignMistakeSignal,
    CampaignMistakeSignalCreate,
    CampaignMistakeState,
)
from backend.domain.models import Campaign

_MISTAKE_ENTRY_SOFT_LIMIT = 12
_MISTAKE_LEVEL_LIMIT = 3
_MISTAKE_TOTAL_COUNT_LIMIT = 99

_PRUNE_CATEGORY_PRIORITY = {
    "invalid_interaction": 0,
    "blocked_attempt": 1,
    "wrong_item": 2,
    "repeated_misuse": 3,
}


def record_mistake_signals(
    campaign: Campaign,
    signals: Iterable[CampaignMistakeSignalCreate | Dict[str, object]],
    *,
    current_turn_index: int,
    turn_id: str,
) -> Dict[str, List[str]]:
    state = _state(campaign)
    recorded_ids: List[str] = []
    touched_ids: Set[str] = set()

    for payload in signals:
        signal = (
            payload
            if isinstance(payload, CampaignMistakeSignalCreate)
            else CampaignMistakeSignalCreate.model_validate(payload)
        )
        signal_id = _signal_id_for(signal)
        now = datetime.now(timezone.utc).isoformat()
        entry = state.entries.get(signal_id)
        if entry is None:
            entry = CampaignMistakeSignal(
                signal_id=signal_id,
                category=signal.category,
                source_tool=signal.source_tool,
                reason=signal.reason,
                target_id=signal.target_id,
                target_label=signal.target_label,
                area_id=signal.area_id,
                item_id=signal.item_id,
                required_item_id=signal.required_item_id,
                metadata=dict(signal.metadata),
                count=1,
                level=1,
                last_turn_index=current_turn_index,
                last_turn_id=turn_id,
                created_at=now,
                updated_at=now,
            )
            state.entries[signal_id] = entry
        else:
            entry.count += 1
            entry.level = min(_MISTAKE_LEVEL_LIMIT, entry.count)
            entry.source_tool = signal.source_tool
            entry.reason = signal.reason
            entry.target_id = signal.target_id or entry.target_id
            entry.target_label = signal.target_label or entry.target_label
            entry.area_id = signal.area_id or entry.area_id
            entry.item_id = signal.item_id or entry.item_id
            entry.required_item_id = signal.required_item_id or entry.required_item_id
            entry.metadata = _merge_metadata(entry.metadata, signal.metadata)
            entry.last_turn_index = current_turn_index
            entry.last_turn_id = turn_id
            entry.updated_at = now
        recorded_ids.append(signal_id)
        touched_ids.add(signal_id)

    if recorded_ids:
        state.total_count = min(
            _MISTAKE_TOTAL_COUNT_LIMIT, state.total_count + len(recorded_ids)
        )
        state.last_turn_index = current_turn_index
        _refresh_state_level(state)
    pruned_ids = prune_campaign_mistakes(campaign, keep_signal_ids=touched_ids)
    if pruned_ids:
        _refresh_state_level(state)
    return {
        "recorded_signal_ids": recorded_ids,
        "pruned_signal_ids": pruned_ids,
    }


def prune_campaign_mistakes(
    campaign: Campaign,
    *,
    keep_signal_ids: Optional[Set[str]] = None,
    soft_limit: int = _MISTAKE_ENTRY_SOFT_LIMIT,
) -> List[str]:
    state = _state(campaign)
    keep = set(keep_signal_ids or set())
    if soft_limit < 1:
        soft_limit = 1
    if len(state.entries) <= soft_limit:
        return []

    removable = sorted(
        (entry for entry in state.entries.values() if entry.signal_id not in keep),
        key=_prune_sort_key,
    )
    pruned_ids: List[str] = []
    while len(state.entries) > soft_limit and removable:
        entry = removable.pop(0)
        if entry.signal_id not in state.entries:
            continue
        del state.entries[entry.signal_id]
        pruned_ids.append(entry.signal_id)
    return pruned_ids


def build_mistake_debug_context(
    campaign: Campaign,
    *,
    recorded_signal_ids: Optional[Iterable[str]] = None,
    pruned_signal_ids: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    state = _state(campaign)
    recorded = list(recorded_signal_ids or [])
    pruned = list(pruned_signal_ids or [])
    entries = _serialize_entries(state.entries.values())
    touched = [
        entry
        for entry in entries
        if isinstance(entry.get("signal_id"), str)
        and entry["signal_id"] in set(recorded)
    ]
    return {
        "slot": "mistake_budget_v1",
        "level": state.level,
        "total_count": state.total_count,
        "last_turn_index": state.last_turn_index,
        "entry_count": len(state.entries),
        "entries": entries,
        "recorded_signal_ids": recorded,
        "recorded_signals": touched,
        "pruned_signal_ids": pruned,
        "soft_limit": _MISTAKE_ENTRY_SOFT_LIMIT,
    }


def build_mistake_state_summary(campaign: Campaign) -> Dict[str, object]:
    state = _state(campaign)
    return {
        "level": state.level,
        "total_count": state.total_count,
        "last_turn_index": state.last_turn_index,
        "entry_count": len(state.entries),
        "categories": sorted({entry.category for entry in state.entries.values()}),
    }


def _state(campaign: Campaign) -> CampaignMistakeState:
    state = getattr(campaign, "mistakes", None)
    if isinstance(state, CampaignMistakeState):
        return state
    normalized = CampaignMistakeState.model_validate(state or {})
    campaign.mistakes = normalized
    return normalized


def _signal_id_for(signal: CampaignMistakeSignalCreate) -> str:
    components = [
        signal.category,
        signal.source_tool,
        signal.reason,
        signal.target_id or "",
        signal.item_id or "",
        signal.required_item_id or "",
    ]
    normalized = re.sub(r"[^a-z0-9]+", "_", "__".join(components).lower()).strip("_")
    return f"mistake_{normalized or 'signal'}"


def _merge_metadata(
    existing: Dict[str, object],
    incoming: Dict[str, object],
) -> Dict[str, object]:
    if not incoming:
        return dict(existing)
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def _refresh_state_level(state: CampaignMistakeState) -> None:
    if not state.entries:
        state.level = 0
        return
    state.level = min(
        _MISTAKE_LEVEL_LIMIT,
        max(entry.level for entry in state.entries.values()),
    )


def _serialize_entries(entries: Iterable[CampaignMistakeSignal]) -> List[Dict[str, object]]:
    return [
        {
            "signal_id": entry.signal_id,
            "category": entry.category,
            "source_tool": entry.source_tool,
            "reason": entry.reason,
            "target_id": entry.target_id or "",
            "target_label": entry.target_label or "",
            "area_id": entry.area_id or "",
            "item_id": entry.item_id or "",
            "required_item_id": entry.required_item_id or "",
            "count": entry.count,
            "level": entry.level,
            "last_turn_index": entry.last_turn_index,
            "last_turn_id": entry.last_turn_id or "",
            "metadata": dict(entry.metadata),
        }
        for entry in sorted(entries, key=_entry_sort_key)
    ]


def _entry_sort_key(entry: CampaignMistakeSignal) -> tuple[int, int, int, str]:
    return (-entry.last_turn_index, -entry.level, -entry.count, entry.signal_id)


def _prune_sort_key(entry: CampaignMistakeSignal) -> tuple[int, int, int, str]:
    category_priority = _PRUNE_CATEGORY_PRIORITY.get(entry.category, 0)
    return (entry.count, category_priority, entry.last_turn_index, entry.signal_id)
