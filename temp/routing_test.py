from backend.services import context_builder, context_config, conversation_store, dialog_router

config = context_config.load_context_config()

conversation = conversation_store.create_conversation()
conversation["summary"] = {"summary_note": "summary-test"}
conversation["key_facts"] = ["fact-a", "fact-b"]
conversation["messages"] = [
    conversation_store.new_message("user", "U1"),
    conversation_store.new_message("assistant", "A1"),
    conversation_store.new_message("user", "U2"),
    conversation_store.new_message("assistant", "A2"),
    conversation_store.new_message("user", "U3"),
    conversation_store.new_message("assistant", "A3"),
]

routes = [
    ("narrative", "scene_pure"),
    ("narrative", "scene_general"),
    ("action_intent", "light"),
    ("rules_query", "explain"),
]

for dialog_type, variant in routes:
    route = dialog_router.resolve_dialog_route(
        config=config,
        dialog_type=dialog_type,
        variant=variant,
        context_profile=None,
        response_style=None,
        guards=None,
    )
    profile = config.context_profiles[route.context_profile]
    messages = context_builder.build_messages(
        conversation=conversation,
        user_text="test-input",
        config=config,
        route=route,
        profile=profile,
        mode=None,
        context_strategy=None,
        persona_lock_enabled=True,
    )
    print("\n==", dialog_type, variant, "=>", route.context_profile)
    for msg in messages:
        preview = msg["content"].replace("\n", " ")[:80]
        print(f"{msg['role']}: {preview}")
