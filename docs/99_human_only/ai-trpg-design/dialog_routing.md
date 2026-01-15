# 对话路由与上下文配置设计文档（规格冻结稿）

## 1) 背景与目标
- 当前仓库已具备 full_context 上下文管线、system prompt 文件加载、注入块拼装、会话存储与 GM persona lock（含运行时漂移检测）等基础能力。
- 本文目标：定义可扩展的“对话路由决策 → 上下文配置档 → 执行管线”协议，作为后续新增 dialog_type/variant/compact_context 的唯一规格来源。
- 规格强调“配置驱动 + 路由表驱动”，避免把业务分支堆入 context_builder。

## 2) 路由决策协议（冻结）
路由决策必须统一产出以下 JSON 对象（手动参数 / 规则分类 / 轻量模型分类最终都输出该对象）：

```json
{
  "dialog_type": "narrative",
  "variant": "scene_pure",
  "context_profile": "nar_scene_pure",
  "response_style": "default",
  "guards": ["persona_lock", "role_confusion_guard"]
}
```

字段定义：
- dialog_type：主类型枚举（建议值：narrative / action_intent / rules_query / meta_control）。
- variant：子类型枚举（在 dialog_type 下定义，例：scene_pure / scene_general / light / explain）。
- context_profile：上下文配置档 ID，必须可直接映射到配置文件中的 profile。
- response_style：响应风格枚举（建议值：default / concise / rules_only / diagnostic）。
- guards：启用的防护策略列表，默认包含 persona_lock 与 role_confusion_guard。

约束：
- context_builder 不得自行推断 dialog_type/variant/context_profile。
- 路由器无论来源，必须生成以上字段（缺字段视为不合规）。
- dialog_route_default 与 dialog_routes 由配置文件提供，允许覆盖默认路由与默认 guards。

## 3) 上下文块类型枚举（冻结）
允许的 block 名称与用途：
- character_sheet：角色卡原文，作为静态背景，不代表身份。
- character_state：角色当前状态摘要（数值/状态仅限外部权威来源摘要）。
- rules_text：规则/协议文本，用于解释规则或约束行为。
- world_state：世界状态摘要（只含 ID/枚举/摘要，不含权威数值细节）。
- lore：世界观与设定背景（稳定的设定文本）。
- session_summary：会话总结（结构化摘要，供重启与压缩）。
- key_facts：关键事实列表（人物/目标/地点/物品/进度）。
- recent_turns：最近 N 轮对话摘要或短文本回放。

信息来源约定：
- character_sheet/character_state/world_state/session_summary/key_facts/recent_turns 均来源于存储或工具生成，不由 LLM 自行推断。
- rules_text/lore 为静态文档或配置文件。
- 路径配置键：character_sheet_path / character_state_path / rules_text_path / world_state_path / lore_path。

## 4) context_profile 配置规格（冻结）
profile 结构（JSON 模板）：

```json
{
  "id": "nar_scene_pure",
  "include_blocks": ["lore", "session_summary", "recent_turns"],
  "exclude_blocks": ["character_sheet", "rules_text"],
  "limits": {
    "lore": 1200,
    "session_summary": 1500,
    "recent_turns": 1200
  },
  "recent_turns_n": 4,
  "strategy": "full_context"
}
```

规则：
- include_blocks 按优先级顺序拼接。
- exclude_blocks 优先级最高；若 include 与 exclude 冲突，必须剔除。
- limits 使用字符数（chars）作为上限；未配置视为不限制。
- recent_turns_n 仅对 recent_turns 生效（compact_context 下启用，且仅当 include_blocks 含 recent_turns）。
- strategy 允许值：full_context / compact_context / auto。
- profiles 与 routes 均存放在 config.json，作为运行时唯一来源。

## 5) 最小可用路由表（V0）
路由规则：dialog_type.variant → context_profile
- narrative.scene_pure → nar_scene_pure
- narrative.scene_general → nar_scene_general
- action_intent.light → act_light
- rules_query.explain → rules_explain

## 6) 最小 context_profiles（V0）
以下配置用于 V0 试跑：

### nar_scene_pure
```json
{
  "id": "nar_scene_pure",
  "include_blocks": ["lore", "session_summary", "recent_turns"],
  "exclude_blocks": ["character_sheet", "rules_text", "character_state"],
  "limits": {
    "lore": 1200,
    "session_summary": 1500,
    "recent_turns": 1200
  },
  "recent_turns_n": 4,
  "strategy": "full_context"
}
```

### nar_scene_general
```json
{
  "id": "nar_scene_general",
  "include_blocks": ["character_state", "world_state", "session_summary", "recent_turns"],
  "exclude_blocks": ["character_sheet", "rules_text"],
  "limits": {
    "character_state": 800,
    "world_state": 800,
    "session_summary": 1500,
    "recent_turns": 1200
  },
  "recent_turns_n": 4,
  "strategy": "full_context"
}
```

### act_light
```json
{
  "id": "act_light",
  "include_blocks": ["character_state", "world_state", "recent_turns"],
  "exclude_blocks": ["character_sheet", "rules_text"],
  "limits": {
    "character_state": 900,
    "world_state": 900,
    "recent_turns": 1200
  },
  "recent_turns_n": 3,
  "strategy": "full_context"
}
```

### rules_explain
```json
{
  "id": "rules_explain",
  "include_blocks": ["rules_text"],
  "exclude_blocks": ["character_sheet", "character_state", "world_state", "lore", "key_facts", "session_summary", "recent_turns"],
  "limits": {
    "rules_text": 2000
  },
  "recent_turns_n": 0,
  "strategy": "compact_context"
}
```

规则补充：
- scene_pure 不带角色卡与规则文本。
- scene_general 可选 character_state，但不带角色卡原文。
- act_light 以 character_state/world_state 为主。
- rules_explain 只读 rules_text，不推进剧情。

## 7) system prompt 选择规则（先定义映射，不强制实现）
映射规则：
- system_prompt = prompts/system/{dialog_type}_{response_style}.txt
- 未找到时回退到 prompts/system/context_full.txt
- 当前可全部指向同一文件，但映射规则必须固定。
 - 若明确传入 mode，则优先使用 prompts/system/{mode}.txt。

默认约束：
- GM persona lock 与 role confusion guard 在所有类型下默认开启。

## 8) 职责边界与禁止事项（强制）
- context_builder 只负责“按 context_profile 拼 messages”，不得判断 dialog_type/variant。
- 不允许把业务分支写进 system prompt。
- 分类/路由不得绕过 GM persona lock。
- 新增类型只能加配置/路由表，不得在 builder 内堆 if-else。

## 9) compact_context 的前置接口约定（仅规格，不实现）
conversation 存储新增最小字段（结构约定）：
- summary：会话摘要（结构化 JSON 或受限文本）。
- key_facts：关键事实集合（JSON 数组）。
- last_summarized_at：ISO 时间戳。
- last_summarized_turn：最后一次摘要时的消息序号。
上述字段仅作为拼装入口，当前不自动生成与更新。

strategy=compact_context 的拼装顺序约定：
1) system prompt
2) session_summary（未被 exclude 时）
3) key_facts（未被 exclude 时）
4) recent_turns
5) 当前 user

约束：
- 当前超长仍直接报错（直到升级策略实现）。
- strategy=full_context 时追加完整历史（user/assistant 全量），recent_turns_n 不参与历史裁剪。
- compact_context 下 character_sheet 只保留高亮字段（id/name/motivation/strengths/flaw/weaknesses 等）。
- compact_context 下 world_state 优先使用摘要字段（summary/summary_note 等），否则回退到精简结构。

## 10) 验收清单（用于确认）
- 路由协议字段冻结
- block 枚举冻结
- profile 配置模板完成
- 4 条最小路由完成
- 4 个最小 profiles 完成
- 禁止事项/职责边界明确

下一步实现建议（仅一段）：读取路由参数并归一化为路由决策对象 → 按路由表找到 context_profile → 由 context_builder 按 profile 规则拼装 messages → 统一进入现有 LLM 调用管线。
