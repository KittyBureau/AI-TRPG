# AI 跑团产品 Agent Spec（V1）
日期：2026-01-14
面向：AI Agent / Codex（实现与扩展时的行为协议与数据草案）

---

## 1. 核心原则（Agent 必须遵守）
1. **权威状态优先**：血量、区域位置、存活状态、世界规则、地图结构、角色卡字段均以系统数据为准。
2. **AI 只提案不裁决**：AI 可以请求工具调用，但是否执行由业务层决定。
3. **对话类型可扩展**：当前由玩家手动选择；未来支持自动路由（需要预留接口）。
4. **冲突必须可修复**：发现冲突要触发“拦截+重试”流程，避免将矛盾输出给玩家。

---

## 2. 会话/战役对象（产品级数据草案）
> 仅为 schema 草案（实现可调整命名与存储形式），但语义需保留。

### 2.1 Campaign（战役）
- campaign_id: string
- title: string（可选）
- created_at / updated_at
- selected:
  - world_id
  - map_id
  - party_character_ids: string[]（多玩家角色集合）
  - active_actor_id: string（当前行动者）
- goal:
  - ultimate_goal_text: string（可隐藏）
  - is_hidden: bool
- milestone:
  - value: int（或 float）
  - last_advanced_at_turn: int
  - advance_policy: object（阈值策略，见 8）
- settings_snapshot: object（见 4）
- state_refs:
  - world_state_id
  - map_state_id
  - summary_state_id
- dialog:
  - dialog_type_selected: string（手动选择）
  - future_route_decision: object?（预留：自动路由输出）

### 2.2 TurnLog（回合日志）
- turn_id: string
- actor_id: string
- user_input: string
- assistant_output_text: string（最终展示文本）
- assistant_structured: object?（结构化结果，如 tool calls、combat log）
- applied_actions: array（已执行动作列表）
- timestamp

### 2.3 SummaryState（摘要）
- summary_text: string
- facts_json: object
- pins: string[]

---

## 3. 角色对象（Character）草案
- character_id: string
- name: string
- title: string
- background: string
- job: string
- race: string
- hp:
  - current: int
  - max: int
- skills:
  - name: string
  - level: int?（可选）
- attributes:
  - strength: int
  - dexterity: int
  - intelligence: int
  - ...（可扩展）
- status:
  - alive_state: enum（例如 alive / downed / dead / restrained_permanent ；后续补充）
  - flags: string[]（可选）

---

## 4. Settings 系统协议（扩展点）

### 4.1 SettingDefinition（定义，注册表）
每个设置项至少包含：
- key: string（例如 "context.compress_enabled"）
- type: enum（bool/int/enum/string/json）
- default: any
- scope: "campaign" | "global"
- validation: 自然语言约束（实现可转为校验器）
- ui_hint: 自然语言（控件类型/提示文案）
- effect_tags: ["context"|"rules"|"routing"|"ui"|"storage"]（影响范围）

### 4.2 SettingsSnapshot（快照）
- 一个 key-value map（campaign 级别）
- 修改允许发生在会话过程中；每次 turn 读取最新快照。

### 4.3 V1 必备设置 keys（建议）
- context.full_context_enabled: bool
- context.compress_enabled: bool（与 full_context 互斥或优先级需定义）
- rules.hp_zero_ends_game: bool
- rollback.max_checkpoints: int（仅保留设计，V1 可不启用）
- dialog.manual_type: enum（scene / action / rules / free_chat）

---

## 5. 对话类型（Dialog Type）协议

### 5.1 手动选择（V1）
- 玩家在对话设置中选择 dialog.manual_type
- ContextBuilder 依据该类型拼装不同提示词块

### 5.2 自动路由（预留）
- route_decision schema（预留字段）：
  - dialog_type
  - variant
  - context_profile
  - guards[]
- 路由输出必须落在 campaign.dialog.future_route_decision（或等价位置）
- V1 不启用，但实现时不得破坏手动选择模式

---

## 6. 工具调用（Action/Tool Call）协议

### 6.1 总原则
- AI 可随时提出 tool call 请求（结构化）
- 业务层基于：
  - allowlist（允许工具清单）
  - 当前状态机
  - 规则设置（settings_snapshot）
  决定是否执行

### 6.2 tool call 请求格式（草案）
assistant_structured.tool_calls: [
  {
    "tool": "move" | "hp_delta" | "map_generate" | "character_generate" | "...",
    "args": { ... },
    "reason": "自然语言理由（可选）",
    "id": "call_001"
  }
]

### 6.3 V1 允许执行的最小工具（建议）
- move：
  - args: { "actor_id": string, "from_area_id": string, "to_area_id": string, "path_id": string? }
- hp_delta：
  - args: { "target_character_id": string, "delta": int, "cause": string }

> 注意：即使 AI 请求了非允许工具，也必须被业务层拒绝并走失败反馈流程。

### 6.4 失败反馈与禁用信息追加（确认规则）
当 tool call 执行失败或被拒绝：
1. 业务层生成 tool_feedback（含失败原因、禁用信息）
2. 将 tool_feedback **append 到上一次 Request**（而不是让 AI 自行猜测）
3. 重新请求生成（计入冲突/重试次数控制）

tool_feedback 草案：
- failed_calls: [
  {
    "id": "call_001",
    "tool": "move",
    "status": "rejected" | "error",
    "reason": "例如：区域移动锁未解除 / 工具未启用",
    "disabled_until": "optional"
  }
]

---

## 7. 冲突检测与重试（必须可配置）

### 7.1 冲突定义
AI 输出文本或结构化内容与权威状态不一致，例如：
- 叙事声称 HP 改变但无对应工具结算
- 宣称角色已进入某区域但系统位置未变
- 改写世界规则/地图结构/角色卡字段

### 7.2 处理流程（V1）
- intercept_output: true
- retry_with_debug: true
- max_retries: K（建议 1–2）
- 超过 K：
  - 返回 conflict_report 给玩家（人工处理分支）

conflict_debug 建议包含：
- expected_state_snippet（权威字段摘要）
- mismatch_reason
- instructions（例如：不得自行改变 HP，请通过 hp_delta tool call 请求）

---

## 8. 里程碑推进（token 压力驱动）

### 8.1 目标生成输入
- world background + map + character background
- ultimate_goal_text 不可改写，可隐藏

### 8.2 推进触发策略（V1 建议默认）
任选一种作为实现口径（实现可配置）：
- by_turn_count：每 N 个 turn 推进 1 次
- by_token_estimate：累计 token 估算超过阈值推进
- by_summary_version：摘要版本增长到阈值推进

### 8.3 推进后的提示词约束（自然语言）
- 系统提示词增加“加速推进事件”的指令：
  - 提升紧迫性
  - 增加线索密度
  - 引导玩家向目标收束
- 但不得越权修改权威状态；需要通过工具请求结算。

---

## 9. 回滚（设计预留，不实现也要留字段）
- checkpoints: [{
    "turn_id": "...",
    "timestamp": "...",
    "label": "可选",
    "state_snapshot_ref": "引用（实现自定）"
  }]
- rollback_pending:
  - is_pending: bool
  - from_turn_id: string
  - to_turn_id: string
  - can_undo: bool（仅在玩家发送新指令前为 true）

规则：
- 回滚后未继续对话：允许撤销
- 回滚后继续对话：不可撤销（形成新分支）

---

## 10. 扩展开发要求（对每个新工具/新功能的约束）
- 每新增一个工具：
  1) 必须在 allowlist 里注册
  2) 必须定义 args schema 与拒绝原因枚举
  3) 必须在冲突检测规则中加入对应校验
  4) 必须在 Agent 文档与人类文档更新（双文档）
