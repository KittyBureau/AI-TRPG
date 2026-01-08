import logging
import re
from typing import Any, Dict, Iterable, List

from backend.services import conversation_store, context_builder, context_config, llm_client

logger = logging.getLogger(__name__)

DEFAULT_MODE = "context_full"
PERSONA_LOCK_RESPONSE = (
    "I am the GM/narrative assistant and cannot take on PC or NPC identities. "
    "I will continue as the GM. What do you do next?"
)
PERSONA_DRIFT_PATTERNS = [
    r"\bI am the PC\b",
    r"\bI'm the PC\b",
    r"\bI am the player character\b",
    r"\bI'm the player character\b",
    r"\bI am your character\b",
    r"\bI'm your character\b",
    r"\bI am an NPC\b",
    r"\bI'm an NPC\b",
    r"\bI am the NPC\b",
    r"\bI'm the NPC\b",
    r"\u6211\u662fPC",
    r"\u6211\u5c31\u662fPC",
    r"\u6211\u662f\u73a9\u5bb6\u89d2\u8272",
    r"\u6211\u5c31\u662f\u73a9\u5bb6\u89d2\u8272",
    r"\u6211\u662fNPC",
    r"\u6211\u5c31\u662fNPC",
    r"\u6211\u662f\u8be5\u89d2\u8272",
]
NPC_LINE_RE = re.compile(r"^\s*NPC\([^)]+\):", re.IGNORECASE)


class ChatServiceError(Exception):
    pass


class ChatRequestError(ChatServiceError):
    pass


class ChatLockedError(ChatServiceError):
    pass


class ChatNotFoundError(ChatServiceError):
    pass


class ChatConfigError(ChatServiceError):
    pass


class ChatLLMError(ChatServiceError):
    pass


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _filter_npc_lines(text: str) -> str:
    lines = text.splitlines()
    kept = [line for line in lines if not NPC_LINE_RE.match(line)]
    return "\n".join(kept)


def _detect_persona_drift(text: str, character_names: Iterable[str]) -> bool:
    if not text:
        return False
    sample = _filter_npc_lines(text)
    for pattern in PERSONA_DRIFT_PATTERNS:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            return True
    names = _dedupe(name.strip() for name in character_names if name and name.strip())
    for name in names:
        escaped = re.escape(name)
        patterns = [
            rf"\bI am {escaped}\b",
            rf"\bI'm {escaped}\b",
            rf"\bI am the {escaped}\b",
            rf"\bI'm the {escaped}\b",
            rf"\u6211\u662f\s*{escaped}",
            rf"\u6211\u5c31\u662f\s*{escaped}",
        ]
        for pattern in patterns:
            if re.search(pattern, sample, flags=re.IGNORECASE):
                return True
    return False


async def send_chat(
    user_text: str,
    conversation_id: str | None = None,
    mode: str | None = None,
    context_strategy: str | None = None,
) -> Dict[str, Any]:
    if not isinstance(user_text, str) or not user_text.strip():
        raise ChatRequestError("user_text must be non-empty text.")

    try:
        config = context_config.load_context_config()
    except context_config.ContextConfigError as exc:
        raise ChatConfigError(str(exc)) from exc

    resolved_mode = mode or DEFAULT_MODE
    resolved_strategy = context_strategy or config.context_strategy

    conversation: Dict[str, Any]
    created_new = False
    if conversation_id:
        conversation_id = conversation_id.strip()
    if conversation_id:
        try:
            lock = conversation_store.acquire_lock(conversation_id)
        except conversation_store.ConversationLockedError as exc:
            raise ChatLockedError(str(exc)) from exc
        except conversation_store.ConversationError as exc:
            raise ChatRequestError(str(exc)) from exc
        try:
            conversation = conversation_store.load_conversation(conversation_id)
        except conversation_store.ConversationNotFoundError as exc:
            lock.release()
            raise ChatNotFoundError(str(exc)) from exc
    else:
        conversation = conversation_store.create_conversation(
            meta={"mode": resolved_mode, "context_strategy": resolved_strategy}
        )
        conversation_id = conversation["conversation_id"]
        created_new = True
        try:
            lock = conversation_store.acquire_lock(conversation_id)
        except conversation_store.ConversationLockedError as exc:
            raise ChatLockedError(str(exc)) from exc
        except conversation_store.ConversationError as exc:
            raise ChatRequestError(str(exc)) from exc

    try:
        messages = context_builder.build_messages(
            conversation=conversation,
            user_text=user_text,
            config=config,
            mode=resolved_mode,
            context_strategy=resolved_strategy,
        )
        assistant_text, usage, params = await llm_client.chat_completion(messages)
        if config.persona_lock_enabled:
            character_names = context_builder.get_character_names(config)
            if _detect_persona_drift(assistant_text, character_names):
                assistant_text = PERSONA_LOCK_RESPONSE

        user_message = conversation_store.new_message("user", user_text)
        assistant_meta: Dict[str, Any] = {}
        if usage and config.log_tokens:
            assistant_meta["token_usage"] = usage
        assistant_message = conversation_store.new_message(
            "assistant",
            assistant_text,
            meta=assistant_meta or None,
        )
        conversation_store.append_messages(conversation, [user_message, assistant_message])
        meta = conversation.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            conversation["meta"] = meta
        meta.update(
            {
                "model": params.get("model"),
                "base_url": params.get("base_url"),
                "provider": params.get("provider"),
            }
        )
        if usage and config.log_tokens:
            meta["last_token_usage"] = usage
        conversation_store.save_conversation(conversation)
    except context_builder.ContextBuilderError as exc:
        raise ChatRequestError(str(exc)) from exc
    except llm_client.LLMError as exc:
        raise ChatLLMError(str(exc)) from exc
    finally:
        lock.release()
        if created_new:
            logger.info("Chat start: new conversation %s", conversation_id)

    response: Dict[str, Any] = {
        "conversation_id": conversation_id,
        "assistant_text": assistant_text,
    }
    if usage and config.log_tokens:
        response["token_usage"] = usage
    return response
