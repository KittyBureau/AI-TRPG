import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONVERSATION_DIR = BACKEND_DIR / "data" / "conversations"

CONVERSATION_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_LOCK_GUARD = threading.Lock()
_LOCKS: Dict[str, threading.Lock] = {}


class ConversationError(Exception):
    pass


class ConversationNotFoundError(ConversationError):
    pass


class ConversationLockedError(ConversationError):
    pass


class ConversationFormatError(ConversationError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_dir() -> Path:
    CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERSATION_DIR


def _conversation_path(conversation_id: str) -> Path:
    return _ensure_dir() / f"{conversation_id}.json"


def _temp_path(conversation_id: str) -> Path:
    return _ensure_dir() / f"{conversation_id}.json.tmp"


def _validate_conversation_id(conversation_id: str) -> None:
    if not isinstance(conversation_id, str) or not CONVERSATION_ID_RE.match(conversation_id):
        raise ConversationError("conversation_id must be a 32-char hex string.")


def _get_lock(conversation_id: str) -> threading.Lock:
    with _LOCK_GUARD:
        lock = _LOCKS.get(conversation_id)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[conversation_id] = lock
    return lock


def acquire_lock(conversation_id: str) -> threading.Lock:
    _validate_conversation_id(conversation_id)
    lock = _get_lock(conversation_id)
    if not lock.acquire(blocking=False):
        raise ConversationLockedError("Conversation is locked by another request.")
    return lock


def create_conversation(meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    conversation_id = uuid.uuid4().hex
    now = _now_iso()
    payload: Dict[str, Any] = {
        "conversation_id": conversation_id,
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "summary": None,
        "key_facts": [],
        "last_summarized_at": None,
        "last_summarized_turn": None,
        "meta": meta or {},
    }
    save_conversation(payload)
    return payload


def load_conversation(conversation_id: str) -> Dict[str, Any]:
    _validate_conversation_id(conversation_id)
    path = _conversation_path(conversation_id)
    if not path.exists():
        raise ConversationNotFoundError(f"Conversation not found: {conversation_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConversationFormatError("Conversation file is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ConversationFormatError("Conversation payload must be a JSON object.")
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise ConversationFormatError("Conversation messages must be a list.")
    return payload


def save_conversation(conversation: Dict[str, Any]) -> None:
    conversation_id = conversation.get("conversation_id")
    _validate_conversation_id(conversation_id)
    conversation["updated_at"] = _now_iso()
    payload = json.dumps(conversation, ensure_ascii=False, indent=2)
    path = _conversation_path(conversation_id)
    temp_path = _temp_path(conversation_id)
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(path)


def new_message(role: str, content: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if role not in {"user", "assistant"}:
        raise ConversationError("Message role must be 'user' or 'assistant'.")
    if not isinstance(content, str) or not content.strip():
        raise ConversationError("Message content must be non-empty text.")
    message: Dict[str, Any] = {
        "role": role,
        "content": content,
        "created_at": _now_iso(),
    }
    if meta:
        message["meta"] = meta
    return message


def append_messages(conversation: Dict[str, Any], messages: List[Dict[str, Any]]) -> None:
    if "messages" not in conversation or not isinstance(conversation["messages"], list):
        raise ConversationFormatError("Conversation messages must be a list.")
    conversation["messages"].extend(messages)
