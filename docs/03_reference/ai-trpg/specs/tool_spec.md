# AI 跑团应用级设计文档（Python 后端 + Web 前端｜低 Token｜多 Agent｜工具写文档）

> 本文将旧的“工作流/节点式实现”改写为「Python Service + Web Client」的可落地原型设计。  
> 核心不变：低 token、多 agent（可选）、工具读写权威存储、严格 JSON 工具调用、一回合最多一次 tool_call、Session 结束必须 summary 写回。

---

## JSON ????
- 3.1 Campaign?`docs/03_reference/ai-trpg/specs/json/3_1_campaign.json`
- 3.2 Session?`docs/03_reference/ai-trpg/specs/json/3_2_session.json`
- 3.3 Player（权威状态示例）?`docs/03_reference/ai-trpg/specs/json/3_3_player.json`
- 3.4 PromptState（低 token：只给 LLM）?`docs/03_reference/ai-trpg/specs/json/3_4_prompt_state.json`
- 3.5 EventLog / AuditLog（工具写入）?`docs/03_reference/ai-trpg/specs/json/3_5_event_log.json`
- 4.1 POST `/session/new` - Request?`docs/03_reference/ai-trpg/specs/json/4_1_session_new_request.json`
- 4.1 POST `/session/new` - Response?`docs/03_reference/ai-trpg/specs/json/4_1_session_new_response.json`
- 4.2 POST `/turn` - Request?`docs/03_reference/ai-trpg/specs/json/4_2_turn_request.json`
- 4.2 POST `/turn` - Response（TurnOutput）?`docs/03_reference/ai-trpg/specs/json/4_2_turn_response.json`
- 4.3 GET `/state` - Response?`docs/03_reference/ai-trpg/specs/json/4_3_state_response.json`
- 4.4 GET `/logs` - Response?`docs/03_reference/ai-trpg/specs/json/4_4_logs_response.json`
- 4.5.1 POST `/tools/player_hp_reduce`（必须包含，兼容子工具） - Request?`docs/03_reference/ai-trpg/specs/json/4_5_1_player_hp_reduce_request.json`
- 4.5.1 POST `/tools/player_hp_reduce`（必须包含，兼容子工具） - Response（ToolResult）?`docs/03_reference/ai-trpg/specs/json/4_5_1_player_hp_reduce_response.json`
- 4.5.2 POST `/tools/summary_writeback`（必须包含） - Request?`docs/03_reference/ai-trpg/specs/json/4_5_2_summary_writeback_request.json`
- 4.5.2 POST `/tools/summary_writeback`（必须包含） - Response?`docs/03_reference/ai-trpg/specs/json/4_5_2_summary_writeback_response.json`
- 4.5.3 POST `/tools/state_patch`（必须包含，推荐唯一白名单工具） - Request?`docs/03_reference/ai-trpg/specs/json/4_5_3_state_patch_request.json`
- 4.5.3 POST `/tools/state_patch`（必须包含，推荐唯一白名单工具） - Response?`docs/03_reference/ai-trpg/specs/json/4_5_3_state_patch_response.json`
- 4.6 错误码（统一结构）?`docs/03_reference/ai-trpg/specs/json/4_6_error_response.json`
- 7.2 Agent I/O（示例 schema，均为短 JSON） - RouterAgent 输出?`docs/03_reference/ai-trpg/specs/json/7_2_router_agent_output.json`
- 7.2 Agent I/O（示例 schema，均为短 JSON） - Controller 输出?`docs/03_reference/ai-trpg/specs/json/7_2_controller_output.json`
- 7.2 Agent I/O（示例 schema，均为短 JSON） - Guard 输出?`docs/03_reference/ai-trpg/specs/json/7_2_guard_output.json`
- 7.2 Agent I/O（示例 schema，均为短 JSON） - GMAgent 输出（含可选 tool_call）?`docs/03_reference/ai-trpg/specs/json/7_2_gm_agent_output.json`
- 7.2 Agent I/O（示例 schema，均为短 JSON） - SummaryAgent 输出?`docs/03_reference/ai-trpg/specs/json/7_2_summary_agent_output.json`
- 10.1 TurnInput Schema?`docs/03_reference/ai-trpg/specs/json/10_1_turn_input_schema.json`
- 10.2 ToolCall Schema?`docs/03_reference/ai-trpg/specs/json/10_2_tool_call_schema.json`
- 10.3 TurnOutput Schema?`docs/03_reference/ai-trpg/specs/json/10_3_turn_output_schema.json`
- 10.4 ToolResult Schema?`docs/03_reference/ai-trpg/specs/json/10_4_tool_result_schema.json`
- 10.5 Summary Schema?`docs/03_reference/ai-trpg/specs/json/10_5_summary_schema.json`

## 1. 概述（目标、非目标、核心约束）

### 1.1 目标
- 提供一个应用级原型：Web 聊天 UI + 状态面板 + 日志面板。
- 后端采用 Python（推荐 FastAPI），负责：
  - 会话管理（campaign/session）
  - LLM/Agents 编排（单 Agent MVP，支持多 Agent 扩展）
  - 校验 LLM 输出协议
  - 执行一次性 Tool 调用（写入权威状态与审计日志）
- 存储采用 SQLite 或 JSON 文件（权威状态）；工具负责读→算→写→审计。

### 1.2 非目标（MVP 不做）
- 不做复杂基础设施：消息队列、分布式事务、K8s、服务网格。
- 不做完整账号体系与付费系统（可用简单 API Key 或 Session Token）。
- 不追求“无限记忆叙事连贯性”：历史叙事不会回灌给 LLM（UI 可保留显示）。

### 1.3 核心约束（必须遵守）
- **AI 不直接读取/缓存/推断权威存储中的数值与状态**：HP、属性、资源等只能由 Tool 从存储读取并写回。
- **每回合最多一次 `tool_call`**：若多次伤害/多项变更，必须合并为一次提交工具（推荐 `state_patch`）。
- **工具调用严格 JSON + 白名单 + 参数校验 + 幂等 + 审计日志**。
- **低 token**：后端喂给 LLM 的输入必须是短 JSON 状态（ID/枚举/摘要），禁止回传完整历史叙事。
- **Session End 必须生成 summary 并写回权威状态**（系统内置步骤，不可选）。
- **Agent 间通信只能短 JSON/枚举/ID**，不得共享长上下文文本。

---

## 2. 系统架构（组件图文字版）

### 2.1 组件
- **Web Client（UI）**
  - Chat Panel：玩家输入与 AI 输出
  - State Panel：读取后端 `/state` 展示权威状态（可含数值，但不进入 LLM prompt）
  - Logs Panel：读取后端 `/logs` 展示审计日志/事件日志
- **Python API（FastAPI）**
  - `SessionService`：创建/加载 session，生成 session_id
  - `TurnService`：处理 `/turn`，编排 Agent、校验输出、执行 Tool（最多一次）
  - `AgentService`：封装 LLM 调用与多 Agent 路由（可选）
  - `ToolService`：工具白名单、schema 校验、幂等键、执行与审计
  - `Storage`：SQLite/JSON 抽象层（仅供 Tool 使用；Agent 禁止直读）
- **LLM Provider**
  - 单 Agent（MVP）或多 Agent（Router/GM/Controller/Guard/Summary 等）
- **Tools（Tool/Endpoint）**
  - 对外表现为 `/tools/*` API（同进程或独立服务均可）
  - 对内负责读写权威状态与日志
- **Storage（权威存储）**
  - SQLite（推荐，事务/并发更简单）或 JSON 文件（简单但需文件锁）

### 2.2 关键数据流
1. UI → `/turn`：发送用户输入（不发送历史叙事）
2. Python API → LLM：发送 **PromptState（短 JSON）+ user_text + allowed_tools**
3. LLM → Python API：返回 `TurnOutput`（含可选 `tool_call`）
4. Python API → Tool Endpoint：最多一次调用，写回权威状态并产生日志
5. UI → `/state`、`/logs`：展示最新状态与日志（不回灌给 LLM）

---

## 3. 数据模型（最小 schema：campaign/session/player/state/event_log）

> 重要：区分 **权威状态（Authoritative State）** 与 **PromptState（给 LLM 的最小闭包）**。

### 3.1 Campaign
JSON ???`docs/03_reference/ai-trpg/specs/json/3_1_campaign.json`

### 3.2 Session
JSON ???`docs/03_reference/ai-trpg/specs/json/3_2_session.json`

### 3.3 Player（权威状态示例）
JSON ???`docs/03_reference/ai-trpg/specs/json/3_3_player.json`

### 3.4 PromptState（低 token：只给 LLM）
JSON ???`docs/03_reference/ai-trpg/specs/json/3_4_prompt_state.json`

### 3.5 EventLog / AuditLog（工具写入）
JSON ???`docs/03_reference/ai-trpg/specs/json/3_5_event_log.json`

---

## 4. API 设计（端点、请求/响应 JSON、错误码）

> 术语约定：  
> - UI/Client 只调用 `/session/*`、`/turn`、`/state`、`/logs`。  
> - Tools 由后端内部调用（也可暴露为独立服务，但必须鉴权）。  
> - LLM 输出协议统一使用 `say` 字段（不使用 `narrative`）。

### 4.1 POST `/session/new`
创建新 session（必要时创建 campaign）。

**Request**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_1_session_new_request.json`

**Response**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_1_session_new_response.json`

### 4.2 POST `/turn`
单回合入口：后端编排 LLM/Agents，最多一次 Tool 调用。

**Request**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_2_turn_request.json`

**Response（TurnOutput）**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_2_turn_response.json`

### 4.3 GET `/state`
给 UI 展示的权威状态（可含数值）。**不得回灌给 LLM prompt**。

**Response**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_3_state_response.json`

### 4.4 GET `/logs`
读取审计日志/事件日志（分页）。

**Response**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_4_logs_response.json`

---

### 4.5 Tools（/tools/*）

> 约束：LLM 输出的 `tool_call.name` 必须在 `allowed_tools` 白名单内；参数必须通过 JSON Schema；工具必须幂等并写审计日志。  
> 推荐：LLM 只调用 `state_patch`（单入口），以保证“一回合最多一次 tool_call”。

#### 4.5.1 POST `/tools/player_hp_reduce`（必须包含，兼容子工具）
**用途**：单一扣血（调试/兼容）；生产建议通过 `state_patch` 聚合调用。

**Request**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_1_player_hp_reduce_request.json`

**Response（ToolResult）**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_1_player_hp_reduce_response.json`

#### 4.5.2 POST `/tools/summary_writeback`（必须包含）
**用途**：Session 结束写入 summary（以及可选的里程碑/压缩记录）。

**Request**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_2_summary_writeback_request.json`

**Response**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_2_summary_writeback_response.json`

#### 4.5.3 POST `/tools/state_patch`（必须包含，推荐唯一白名单工具）
**用途**：一回合一次性提交：状态变更（如扣血/状态变更/风险升级）+ 可选 summary 写回 + 审计日志。  
**优势**：满足“一回合最多一次 tool_call”，避免 session_end 需要第二次工具调用。

**Request**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_3_state_patch_request.json`

**Response**
JSON ???`docs/03_reference/ai-trpg/specs/json/4_5_3_state_patch_response.json`

---

### 4.6 错误码（统一结构）
所有 API/Tool 统一返回：
JSON ???`docs/03_reference/ai-trpg/specs/json/4_6_error_response.json`

建议错误码集合：
- `INVALID_REQUEST`：请求缺字段/类型错误
- `SESSION_NOT_FOUND` / `CAMPAIGN_NOT_FOUND`
- `LLM_OUTPUT_INVALID_JSON`：LLM 输出不是合法 JSON
- `LLM_OUTPUT_SCHEMA_MISMATCH`：JSON 结构不符合 TurnOutput schema
- `TOOL_NOT_ALLOWED`：tool_call.name 不在白名单
- `TOOL_ARGUMENT_INVALID`：参数 schema 校验失败
- `TOOL_FAILED`：工具执行失败（含存储错误）
- `DUPLICATE_TURN`：turn_id 重复（幂等命中，返回已执行结果或拒绝）
- `CONFLICT`：并发写冲突（乐观锁失败/事务冲突）
- `RATE_LIMITED`：限流

---

## 5. 回合处理流程（/turn 的步骤，含校验与工具调用时序）

> 关键目标：LLM 不读权威数值；一回合最多一次工具调用；失败可恢复；输出可审计。

### 5.1 `/turn` 时序（文字版）
1. **请求校验**：检查 `campaign_id/session_id/turn_id/user_text/intent`
2. **幂等检查（Turn 级）**：
   - 若 `turn_id` 已处理：返回上次 TurnOutput（或返回 `DUPLICATE_TURN`，按产品策略）
3. **加载 PromptState（最小闭包）**：
   - 从 Session 的 `summary`、`milestone_id`、风险/信息档位等生成短 JSON
   - **不加载**玩家 HP/库存等数值到 prompt
4. **LLM 编排**：
   - MVP：单次 LLM 调用输出 TurnOutput（含可选 tool_call）
   - 多 Agent：Router/Controller/Guard/GM/Summary 等（见第 7 章）
5. **输出协议校验**：
   - 必须是严格 JSON
   - `tool_call` ≤ 1
   - `say` 为字符串；`options` 数量/长度受限
6. **工具调用校验**（若 tool_call 存在）：
   - name 在 `allowed_tools`
   - arguments 通过 Tool schema
   - 若 `intent == "end_session"`：必须携带 `summary`（通过 `state_patch` 或 `summary_writeback`）
7. **执行工具（最多一次）**：
   - 调用 `/tools/state_patch`（推荐）或其它被允许工具
   - 工具内部：读→算→写→审计；幂等键确保重复请求不重复写
8. **写 TurnLog（服务器侧）**：
   - 记录：输入摘要、LLM 输出摘要、tool_result（不把数值回灌给 LLM）
9. **返回 UI**：
   - `say`、`options`、`tool_result`（可选）
10. **Session End 分支**：
   - 若 end_session：将 session 状态置为 `ended`（通过 `state_patch` 或 summary 工具写回）

### 5.2 失败路径（必须实现）
- LLM 输出非 JSON：
  - 触发一次“Repair 模式”LLM 调用：只修 JSON，不改语义；仍失败则返回 `LLM_OUTPUT_INVALID_JSON`
- tool_call 不在白名单 / 参数不合规：
  - 返回 `TOOL_NOT_ALLOWED` / `TOOL_ARGUMENT_INVALID`；并记录审计事件
- 工具执行失败（存储/冲突）：
  - 返回 `TOOL_FAILED` 或 `CONFLICT`
  - 可安全重试：依赖 `idempotency_key` 保证不重复写

---

## 6. 低 token 策略（state-only、ID 引用、summary 覆盖、输出限额）

### 6.1 PromptState Only
- LLM 输入只包含：
  - `PromptState`（短 JSON：scene_id/actors/milestone/risk/info/last_event/intent/allowed_tools）
  - `user_text`
  - 少量 “summary_id 列表”或“压缩要点”（严限条目）
- 明确禁止：
  - 把 UI 聊天历史全文拼回 prompt
  - 把权威数值（HP/金钱/库存详细）塞回 prompt

### 6.2 ID + 枚举取代长文本
- 场景/角色/事件/线索只用 ID 引用：`scene_001`, `npc_02`, `clue_17`
- 风险、信息清晰度、里程碑使用枚举：`R0..R4`, `IC0..IC3`, `M0..M5`

### 6.3 Summary 覆盖（强制）
- 每个 Session 结束必须生成 `Summary` 并写回存储。
- Summary 应“覆盖式更新”（替换旧 summary），避免无限增长。

### 6.4 输出限额（防 token 漫延）
- `say`：建议 ≤ 1200 字符（超出则截断或要求 LLM 重写）
- `options`：建议 3–6 个，每个 `text` ≤ 60 字符
- 内部日志可完整，但 LLM 输入必须严格裁剪

---

## 7. 多 agent 方案（职责、输入最小闭包、I/O schema）

> 可选：MVP 用单 Agent；扩展时再拆分。拆分原则：每个 Agent 只拿到完成任务所需的最小闭包，并输出短 JSON。

### 7.1 推荐 Agent 列表
- `RouterAgent`：判定本回合类型（continue/end_session/meta_question）
- `MainlineControllerAgent`：里程碑门槛检查、偏离矫正建议
- `GuardAgent`：现实护栏触发、异常累计与风险复利升级建议
- `GMAgent`：玩家可见叙事与选项（可给 `p_success`）
- `SummaryAgent`：session_end 时生成 Summary JSON
- `ResolverAgent`（可选）：若启用概率层，负责将 `p_success` 变成可执行的工具意图（但不掷骰/不读数值）

### 7.2 Agent I/O（示例 schema，均为短 JSON）

**RouterAgent 输出**
JSON ???`docs/03_reference/ai-trpg/specs/json/7_2_router_agent_output.json`

**Controller 输出**
JSON ???`docs/03_reference/ai-trpg/specs/json/7_2_controller_output.json`

**Guard 输出**
JSON ???`docs/03_reference/ai-trpg/specs/json/7_2_guard_output.json`

**GMAgent 输出（含可选 tool_call）**
JSON ???`docs/03_reference/ai-trpg/specs/json/7_2_gm_agent_output.json`

**SummaryAgent 输出**
JSON ???`docs/03_reference/ai-trpg/specs/json/7_2_summary_agent_output.json`

### 7.3 工具调用权限
- 建议：所有 Agent **都不直接调用工具**；只有 `TurnService` 可以执行工具（最多一次），并且只执行白名单工具。

---

## 8. 可靠性与安全（鉴权、幂等键、审计、重试、并发控制）

### 8.1 鉴权与隔离
- UI API：基于 Session Token 或简单 API Key（MVP 可弱化，仍建议有基础鉴权）。
- Tools API：必须有内部鉴权（`X-Tool-Token`），避免被外部绕过后端校验直接改状态。
- LLM prompt 输入与 UI state 输出隔离：禁止把 `/state` 响应直接拼进 prompt。

### 8.2 幂等（必须）
- Turn 级幂等：`turn_id` 唯一；重复请求返回同一结果或拒绝。
- Tool 级幂等：`idempotency_key` 唯一；重复调用不重复写入。
- 建议幂等键格式：`{campaign_id}:{session_id}:{turn_id}:{op}`。

### 8.3 审计日志（必须）
- 每次工具变更必须追加 `AuditLog`：
  - before/after（可存完整数值，但不回灌给 LLM）
  - source、reason、timestamp、idempotency_key

### 8.4 重试策略
- LLM 调用失败：指数退避重试（有限次数），仍失败返回 `TOOL_FAILED`/`LLM_UNAVAILABLE`（可扩展）
- Tool 调用失败：仅在幂等保障下允许重试

### 8.5 并发控制
- SQLite：事务 +（可选）乐观锁 `state_version`
- JSON：文件锁（按 campaign/session 粒度）+ 写入原子替换
- 冲突统一返回 `CONFLICT`，由 UI 重试或提示用户稍后再试

---

## 9. MVP 里程碑与任务清单（含 DoD）

### M0：最小可用（单 Agent + 单工具）
**目标**
- UI 能对话；后端能生成 `say + tool_call`；工具能写权威状态与审计日志。

**任务**
1. 实现 `/session/new`、`/turn`、`/state`、`/logs`
2. 实现工具 `/tools/player_hp_reduce`（含幂等与审计）
3. 实现 TurnOutput schema 校验（tool_call ≤ 1、白名单、参数校验）

**DoD**
- 一次回合最多一次工具调用；重复 turn/tool 不重复扣血；日志可追溯；LLM 未读取权威数值。

### M1：低 token 强化 + Session Summary（强制）
**任务**
1. 实现 `PromptState` 生成与硬限额（options 数量、say 长度）
2. 增加 `SummaryAgent` 与 `/tools/summary_writeback`
3. `/turn intent=end_session` 强制 summary 写回

**DoD**
- 结束 session 必定写入 summary；下一次只凭 summary 能继续（无历史叙事回灌）。

### M2：多 Agent（可选）与主线护栏
**任务**
1. 增加 Router/Controller/Guard 拆分（输入最小闭包）
2. 引入里程碑门槛与偏离矫正策略（仅输出短 JSON/ID）

**DoD**
- 里程碑未达成不推进；偏离会被矫正回流；异常累计驱动风险复利。

### M3：一次提交工具（满足“一回合一次 tool_call”）
**任务**
1. 实现 `/tools/state_patch`：支持多 op + 可选 summary + 审计
2. 将 LLM 白名单工具收敛为 `state_patch`
3. 增加并发控制与端到端回归用例（无效 JSON、工具失败、重复调用、并发写）

**DoD**
- 任意复杂回合（多伤害+summary）也能通过一次 `state_patch` 完成；并发/重放安全。

---

## 10. 附录：JSON Schema（TurnInput/TurnOutput/ToolCall/ToolResult/Summary）

> 说明：以下 schema 用于后端校验与工具参数校验（可复制使用）。  
> 为便于原型落地，示例采用 draft-07 风格（不依赖复杂关键字）。

### 10.1 TurnInput Schema
JSON ???`docs/03_reference/ai-trpg/specs/json/10_1_turn_input_schema.json`

### 10.2 ToolCall Schema
JSON ???`docs/03_reference/ai-trpg/specs/json/10_2_tool_call_schema.json`

### 10.3 TurnOutput Schema
JSON ???`docs/03_reference/ai-trpg/specs/json/10_3_turn_output_schema.json`

### 10.4 ToolResult Schema
JSON ???`docs/03_reference/ai-trpg/specs/json/10_4_tool_result_schema.json`

### 10.5 Summary Schema
JSON ???`docs/03_reference/ai-trpg/specs/json/10_5_summary_schema.json`

