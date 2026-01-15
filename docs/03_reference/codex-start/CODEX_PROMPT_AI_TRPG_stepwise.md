# 给 Codex 的实现提示词（分阶段、可控代码生成）
日期：2026-01-14

> 目标：让 Codex **逐步**完成 AI 跑团后端项目的最小可用版本，并在每个阶段产出**可衔接的文档**。  
> 约束：实现必须遵守《PRD-lite V1.1》与《Agent Spec V1.1》。  
> 交付：每阶段必须包含“代码变更 + 文档 + 最小测试/手工验证步骤”。

---

## 0) 你要先做的事（Codex 读完再动手）

### 0.1 输入材料（必须阅读）
请在仓库中找到并阅读以下两份文档（若不在仓库根目录，请搜索文件名）：
- `AI_TRPG_PRD-lite_V1.1_SYNC.md`
- `AI_TRPG_Agent_Spec_V1.1_FULL.md`

阅读后用 **5–10 条要点**总结“不可违背的行为边界”。

### 0.2 开发纪律（必须遵守）
1. **分阶段提交**：每阶段只做该阶段范围内的内容，不得顺手“顺便重构”。
2. **配置优先**：规则/类型/允许工具应优先通过配置与注册表扩展。
3. **可复现**：状态写入必须是确定性的；同一输入在同一存档下应产生一致状态演进（在允许的随机范围内也要可控）。
4. **可审计**：每次 Turn 必须落盘：输入、AI 输出、结构化 tool_calls、执行结果、状态摘要。
5. **文档先行**：每阶段必须更新/新增 `docs/` 下的对应文档。

### 0.3 禁止事项（硬禁）
- AI 不得直接修改权威状态（HP/位置/状态/规则/地图结构/角色卡字段）。
- 状态变化只能通过工具请求，由业务层裁决执行。
- 不得把“路由/决策”写进 ContextBuilder（ContextBuilder 只拼装）。

---

## 1) 项目分层与目录（若仓库已有结构，以“最小侵入”对齐）

建议目录（可按项目实际微调，但要保持语义一致）：
- `backend/api/`：FastAPI endpoints（只做 transport）
- `backend/app/`：Use-case / Application Services（Turn 编排、裁决、落盘）
- `backend/domain/`：纯业务规则（router、context builder、validators、settings）
- `backend/infra/`：存储与外部依赖（file repo、LLM client、locks）
- `storage/`：本地数据目录（若现有路径不同，需在文档说明映射）
- `docs/`：项目文档（每阶段必须增量更新）

---

## 2) 分阶段任务清单（按顺序完成）

> 每阶段输出必须包含：
> - ✅ 完成内容列表（What）
> - ✅ 关键决策点（Why）
> - ✅ 文件清单（新增/修改）
> - ✅ 手工验证步骤（How to verify）
> - ✅ docs 更新（至少 1 份）

### 阶段 1：Turn 最小闭环（不接 LLM，先用 FakeLLM）
**目标**：跑通 “输入 → 生成输出 → 落盘” 的最小闭环，保证架构边界正确。

**必须实现**
1. `Campaign`（战役）最小存档结构（JSON）：
   - selected: world_id, map_id, party_character_ids, active_actor_id
   - settings_snapshot（至少包含 dialog 类型与 context 开关）
   - goal/milestone 的最小字段（可先占位）
2. `TurnLog` 追加写入：每次输入生成一条 turn 记录
3. `FakeLLM`：根据输入回显，并可返回一个空的 `tool_calls` 数组
4. FastAPI 最小接口：
   - `POST /api/campaign/create`：创建战役（最小字段）
   - `GET /api/campaign/list`：列出战役
   - `POST /api/campaign/select_actor`：切换行动者
   - `POST /api/chat/turn`：提交一次 turn（暂不执行工具）

**文档要求**
- `docs/01_specs/architecture.md`：分层与职责（简版）
- `docs/01_specs/storage_layout.md`：存档文件结构与字段说明（最小版）

**验收标准**
- 能创建战役、选择行动者、发送 turn，存档中可看到 turn_log 追加增长。

---

### 阶段 2：Settings 注册表 + DialogType 自动判断（不接 LLM，仍用 FakeLLM）
**目标**：把“可扩展设置”和“自动对话类型判断”放到正确层级。

**必须实现**
1. `SettingDefinition` 注册表（至少 5 个 key）：
   - `context.full_context_enabled`
   - `context.compress_enabled`
   - `rules.hp_zero_ends_game`
   - `rollback.max_checkpoints`（仅保存，不启用）
   - `dialog.auto_type_enabled`（默认 true）
2. `GET /api/settings/schema`：返回 definitions + 当前战役 snapshot
3. `POST /api/settings/apply`：对当前战役设置打 patch 并校验
4. `DialogTypeClassifier`：**基于规则（非 LLM）**的最小自动判断（例如关键词/模式），输出：
   - `scene_description | action_prompt | resolution_summary | rule_explanation`
5. Turn 落盘中必须记录 `dialog_type`（来自自动判断）

**文档要求**
- `docs/01_specs/settings.md`：settings 定义、patch、校验与扩展方式
- `docs/01_specs/dialog_types.md`：对话类型定义与判定规则（当前为规则引擎，未来可换模型）

**验收标准**
- 修改设置会影响 turn 记录中的 dialog_type 或 context_profile（可先是字段变化）。

---

### 阶段 3：工具协议（move / hp_delta / map_generate）+ allowlist 裁决（仍不接真实 LLM）
**目标**：实现 Agent Spec 的核心：AI 只能“请求”，系统裁决执行。

**必须实现**
1. ToolCall 结构（id/tool/args/reason）与 ToolFeedback（failed_calls）
2. allowlist：战役级允许工具清单（默认允许 move/hp_delta/map_generate）
3. 状态机：实现 5 种状态与行为限制（alive/dying/unconscious/restrained_permanent/dead）
4. 执行裁决规则：
   - dying 只能对话：拒绝 move/hp_delta（除非是被治疗导致 hp_delta 正向？此处按你理解写进规则并文档化）
   - unconscious：当前 actor 的 turn 可记录但不得执行行动类工具；多人时应允许切换 actor
5. `POST /api/tools/execute`（内部使用或由 `/api/chat/turn` 触发）：
   - 执行成功则写入 applied_actions
   - 执行失败则生成 tool_feedback 并触发一次“重试生成”（此阶段仍用 FakeLLM，可模拟“收到反馈后改写输出”）
6. 世界/地图最小数据：
   - map: areas + connections（区域与边）
   - actor position: area_id

**文档要求**
- `docs/01_specs/tools.md`：工具清单、参数、拒绝原因枚举、失败反馈
- `docs/01_specs/state_machine.md`：状态与工具裁决矩阵（强烈建议表格）

**验收标准**
- move 能更新位置；hp_delta 能更新血量；不满足条件会产生 tool_feedback。

---

### 阶段 4：接入真实 LLM（OpenAI 兼容），实现冲突拦截与重试
**目标**：替换 FakeLLM 为真实 LLM Client，落实冲突拦截与 debug 重试流程。

**必须实现**
1. `LLMClient`（OpenAI 兼容）：支持 base_url + api_key + model + temperature（从本地配置读取）
2. Prompt 组装：
   - ContextBuilder 仅拼装（summary/character/world/map/settings/dialog_type）
   - 不做路由决策（路由来自 dialog_type classifier 或后续模型）
3. 输出协议：AI 输出必须包含：
   - text（叙事）
   - structured.tool_calls（可为空）
4. 冲突检测：
   - 若叙事声称状态变化但无对应 applied_actions
   - 或 tool_calls 请求越权（工具未允许/状态不允许）并且 AI 又宣告已发生
   → 触发拦截
5. 重试：
   - 在上一次 request 后 append conflict_debug/tool_feedback
   - 最多重试 K 次（默认 2）
   - 超过则返回 conflict_report（结构化）

**文档要求**
- `docs/07_llm_prompt_contract.md`：输入块结构、输出结构、示例
- `docs/08_conflict_handling.md`：冲突定义、拦截策略、重试策略、终止策略

**验收标准**
- LLM 输出若越权会被拦截并重试；最终返回要么是合规输出，要么是 conflict_report。

---

### 阶段 5：里程碑推进（token/压力驱动）+ 子地图二次生成闭环
**目标**：实现“节奏控制器”与子地图生成工具真正可用。

**必须实现**
1. 里程碑字段落盘：value + last_advanced_turn + policy
2. 推进策略（默认可选其一）：
   - by_turn_count（每 N 回合推进）或 by_token_estimate（估算 token 超阈值推进）
3. 推进后对 prompt 的影响：增加“加速推进事件”的 system 指令（但仍不得越权）
4. map_generate：生成 parent_area 下的子区域与连接，写入 map 数据
5. 保证一次事件/战斗发生在一个 area 内（体现为：action_prompt 不得跨区域结算；或 tool 执行层限制）

**文档要求**
- `docs/09_milestones.md`：里程碑字段、推进策略、对叙事约束
- `docs/10_map_hierarchy.md`：区域层级、子地图生成规则与边界

**验收标准**
- 可在对话中触发 map_generate，并在存档中看到子区域增加；里程碑在达到阈值后推进。

---

## 3) 关键输出格式（实现必须遵守）

### 3.1 /api/chat/turn 的响应（建议）
- narrative_text: string
- dialog_type: string
- tool_calls: []
- applied_actions: []
- tool_feedback: object?（失败时）
- conflict_report: object?（最终失败时）
- state_summary: object（HP、位置、状态等摘要）

### 3.2 存档必须可审计
每个 Turn 至少落盘：
- user_input
- assistant_text
- assistant_structured.tool_calls
- applied_actions
- state_summary（最小字段即可）
- timestamps

---

## 4) 文档交付要求（强制）
每阶段结束必须更新 `docs/`，并在 `docs/00_overview/README.md` 中维护目录与最新版本号。

文档分两类：
1. **人类读**：解释“产品语义与边界”
2. **Agent/Codex 读**：解释“字段、协议、示例、验收步骤”

---

## 5) Codex 输出格式要求（为了可控）
请按以下顺序输出：
1. 本阶段的“计划清单”（5–15 条）
2. 文件树变更摘要（新增/修改）
3. 关键数据结构（JSON 示例）
4. 关键接口（请求/响应示例）
5. 实现完成后提供手工验证步骤
6. 提供 docs 更新说明

> 除非我明确要求，否则不要一次性输出所有阶段的代码。  
> 每阶段完成后等待我确认再进入下一阶段。

---

## 6) 从阶段 1 开始执行
现在请你从「阶段 1：Turn 最小闭环」开始：
- 先输出“计划清单 + 文件树变更摘要 + 存档 JSON 示例 + 接口示例 + 手工验证步骤 + docs 列表”
- 不要直接输出全部代码（我确认后你再输出代码）。
