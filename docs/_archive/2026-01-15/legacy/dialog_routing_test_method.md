# 对话路由测试方法



## 目标

在不修改业务逻辑的前提下，验证对话路由决策、上下文 profile 选择、块包含/排除以及 guard 行为。



## 前置条件

- `config.json` 包含 `dialog_routes` 与 `context_profiles`（必要时从 `backend/storage/config_template.json` 复制）。

- 如需验证 rules-only 输出，确保 `~/.ai-trpg/config.json` 中设置了 `rules_text_path`。

- 如需测试 `character_state`/`lore` 块，设置 `character_state_path` / `lore_path` 指向可读文件或目录。

- 以下命令均在仓库根目录执行。



## 方法 A：离线拼装消息（无 LLM 调用）

运行下面的片段，检查每个 route profile 组装出的消息列表。



```python

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

    print("

==", dialog_type, variant, "=>", route.context_profile)

    for msg in messages:

        preview = msg["content"].replace("

", " ")[:80]

        print(f"{msg['role']}: {preview}")

```



预期检查点：

- 当 profile 策略为 `compact_context` 时，`rules_query.explain` 只包含 rules 块（无历史、无 key_facts、无角色/世界状态）。

- `narrative.scene_pure` 排除角色卡与规则文本。

- `narrative.scene_general` 与 `action_intent.light` 在路径存在时包含 character_state/world_state。

- 只有在 `context_strategy` 解析为 `compact_context` 时，`recent_turns_n` 才限制历史。



说明：`conversation_store.create_conversation()` 会在 `backend/data/conversations/` 下写入文件。测试完成后如需可手动删除。



## 方法 B：API 层路由检查（需要 LLM 访问）

1) 启动服务：



```powershell

cd path/to/ai-trpg

python -m uvicorn backend.app.main:app --reload

```



2) 调用 `/api/chat/send` 并显式指定路由字段（UTF-8 安全）：



```powershell

$utf8 = [System.Text.UTF8Encoding]::new($false)

[Console]::InputEncoding = $utf8

[Console]::OutputEncoding = $utf8



$body = @{

  user_text = "Explain the rules only."

  dialog_type = "rules_query"

  variant = "explain"

  response_style = "default"

} | ConvertTo-Json



Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/chat/send `

  -ContentType "application/json; charset=utf-8" `

  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

```



3) 查看 `backend/data/conversations/` 下的会话文件并验证：

- `meta.dialog_route.dialog_type`、`variant`、`context_profile` 与请求匹配。

- `meta.dialog_route.context_strategy` 与解析后的 profile 策略一致。

- `meta.dialog_route.guards` 与 guard 列表一致（默认或覆盖）。



预期检查点：

- 响应正常返回，会话元数据记录了路由解析结果。



## 通过标准

- 对四个 V0 路由，路由解析返回期望的 `context_profile`。

- profile 的块包含/排除符合 `docs/03_reference/design/dialog_routing.md` 的设计规则。

- `meta.dialog_route.guards` 中包含 guard 列表，且 persona lock 在触发时生效。



## 可选：Compact Context 抽查

- 将 `context_strategy` 设为 `compact_context`（请求覆盖或 profile 默认）。

- `character_sheet` 仅包含摘要字段（id/name/motivation/strengths/flaw/weaknesses 等）。

- `world_state` 仅包含摘要字段或紧凑结构（time、ids、counts）。

- `recent_turns` 只在 profile 包含且未排除时出现。

