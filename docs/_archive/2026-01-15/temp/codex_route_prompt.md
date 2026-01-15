你现在在我的代码仓库中，帮我生成一份“写代码前的前置设计文档”，用于我确认后再开始实现路由与可扩展上下文选择。注意：我不需要你实现代码，只需要产出文档草案。

目标文档：
- 文件路径：docs/design/dialog_routing.md（如目录不存在请创建）
- 文档必须可作为后续实现的“唯一规格来源”：字段、枚举、配置结构、约束一旦确认就冻结。

你必须阅读（以仓库实际存在为准）：
- README.md（规范入口）
- AI_INDEX.md（如存在）
- docs/ 下与上下文/GM身份锁/注入相关的文档（例如 TODO_CONTEXT.md）
- config_template.json / context_full.txt 等配置与 prompt 脚手架
- 当前 /api/chat/send、context_builder、context_config、conversation_store 等模块的高层结构（只理解职责，不逐行）

写作原则：
- 只做“功能与接口规格”，避免逐函数解释
- 不要发散设计；所有内容必须可落地为配置或简单路由逻辑
- 明确“禁止事项/职责边界”，防止未来扩展时污染 context_builder

文档必须包含以下章节（顺序可微调，但不得缺失）：

1) 背景与目标
- 当前已具备 full_context 上下文管线与 GM persona lock 等基础能力
- 本文目标：定义可扩展的“对话路由决策 → 上下文配置档 → 执行管线”协议，便于后续新增 dialog_type/variant/compact_context

2) 路由决策协议（冻结）
- 定义一个标准 JSON 对象（必须给示例）：
  - dialog_type
  - variant
  - context_profile
  - response_style
  - guards
- 明确：手动参数 / 规则分类 / 轻量模型分类，最终都必须产出该对象
- 明确：context_builder 不得自行推断 dialog_type/variant

3) 上下文块类型枚举（冻结）
- 列出允许的 block 名称与一句话用途说明：
  - character_sheet / character_state / rules_text / world_state / lore / session_summary / key_facts / recent_turns
- 说明每类 block 的信息来源与典型用途

4) context_profile 配置规格（冻结）
- 定义 profile 的配置结构（JSON 模板即可）：
  - include_blocks（按优先级）
  - exclude_blocks
  - limits（先用 chars）
  - recent_turns_n
  - strategy（full_context / compact_context / auto）
- 说明 include/exclude 冲突时的规则（例如 exclude 优先）

5) 最小可用路由表（V0）
- 定义 routes 映射规则：dialog_type.variant → context_profile
- 给出至少 4 条最小路由（用于测试）：
  - narrative.scene_pure → nar_scene_pure
  - narrative.scene_general → nar_scene_general
  - action_intent.light → act_light
  - rules_query.explain → rules_explain

6) 最小 context_profiles（V0）
- 为上面 4 个 profile 写完整配置（include/exclude/limits/recent/strategy）
- 规则要符合当前项目方向：
  - scene_pure 不带角色卡与规则文本
  - scene_general 可选 character_state，但不带角色卡原文
  - act_light 以 character_state/world_state 为主
  - rules_explain 只读 rules_text，不推进剧情

7) system prompt 选择规则（先定义映射，不强制实现）
- 定义如何从 dialog_type/response_style 选择 system prompt 文件
- 允许当前都指向同一 prompt，但映射规则必须写清楚
- 必须声明：GM persona lock 与 role confusion guard 在所有类型下默认开启

8) 职责边界与禁止事项（强制）
至少写明：
- context_builder 只负责“按 context_profile 拼 messages”，不得判断 dialog_type/variant
- 不允许把业务分支写进 system prompt
- 分类/路由不得绕过 GM persona lock
- 新增类型只能加配置/路由表，不能在 builder 里堆 if-else

9) compact_context 的前置接口约定（仅规格，不实现）
- 写清 conversation 存储将新增的最小字段（summary/key_facts/last_summarized_*）
- 写清 strategy=compact_context 时 messages 的拼装顺序约定（summary/facts/recent）
- 明确：当前超长仍直接报错（直到升级策略）

10) 验收清单（用于我确认）
列出 6 条“我确认通过即可开工”的条件：
- 路由协议字段冻结
- block 枚举冻结
- profile 配置模板完成
- 4 条最小路由完成
- 4 个最小 profiles 完成
- 禁止事项/职责边界明确

输出要求：
- 只提交/修改 docs/design/dialog_routing.md（必要时创建目录）
- 在文档末尾附上“下一步实现建议（仅一段）”：读取路由参数→查 routes→取得 profile→builder 拼装
- 不要写代码，不要新增其他文件（除非目录不存在需要创建）
完成后给出文件路径与简要变更摘要（不要长篇解释）。
