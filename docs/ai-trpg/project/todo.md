# 多 Agent 跑团系统｜待办清单（中文）

> 目标：落地「AI 叙事 + 工具结算（读写文档）」的多 Agent 架构，控制 token，确保一次对话最多一次 tool_call，所有状态仅存文档，AI 不读/不缓存文档数值。

## 现有资产（已在仓库内）
- `../prompts/multi_agent_task_prompt.md`：多 Agent + 里程碑任务要求（总提示词）
- `../specs/tool_spec.md`：最小工具结算规范（示例：`player_hp_reduce`）
- `../design/framework.md`：框架总览（多 Agent / 工具链 / 压缩 / 可选概率）
- `../design/mainline_milestones.md`：里程碑门槛、偏离矫正、终局触发、异常累计与特殊效果
- `../design/mainline_protection_mechanism.md`：信息焦点 / 风险阶梯 / 复利式风险
- `../design/reality_guards.md`：现实护栏库（执法、路人传播、经济、风控等）
- `../design/probabilistic_resolution_layer.md`：可选 D20 概率裁定层（成功率由 AI 给、掷骰与能力由工具）
- `../runs/2026-01-06_trpg_test/milestone_log.md`：里程碑式压缩记录（示例，可迁移为 JSON summary）

---

## 里程碑 M0：最小闭环（单工具 + 严格协议）

### 目标
- 跑通：一次对话 → LLM 输出 JSON（叙事 + 可选 tool_call）→ 后端协议校验 → 调用 1 次工具 → 返回。
- 工具实现“读→算→写→记日志”，并具备幂等能力（防重扣）。

### 交付物
- 统一的 AI 输出协议 JSON Schema（含字段命名一致性）
- 后端最小请求流程（`/turn` → LLM → 校验 → Tool → Respond）
- `player_hp_reduce` 工具服务（含文档存储与审计日志）

### 任务清单
- [ ] 统一输出协议字段：以 `say` 为准（如历史兼容需要，可在 API 层做 `narrative -> say` 别名映射）
- [ ] 定义并落地 JSON Schema：`{say, tool_call{name, arguments}}`
- [ ] 后端增加“强校验”：JSON 合法、tool_call ≤ 1、工具白名单、参数校验
- [ ] 实现工具服务端：`POST /tools/player_hp_reduce`
  - [ ] 参数校验（amount ≥ 0 且整数）
  - [ ] 文档读取（campaign_id + player_id）
  - [ ] 扣减并写回（不返回给 AI 的数值仍可返回给前端/日志）
  - [ ] 写审计日志（log_id）
  - [ ] 幂等：同 `campaign_id+player_id+session_id+type` 重放不重复扣血
- [ ] 工具鉴权（token/secret）与错误码规范（与 `../specs/tool_spec.md` 对齐）

### DoD（验收）
- 任意一轮对话最多一次 tool_call；重复触发不重复扣血；日志可追溯；LLM 从未读取或推断文档数值。

---

## 里程碑 M1：多 Agent 上线（路由 + 主线门槛 + 风险护栏）

### 目标
- 把 LLM 逻辑拆成“最小输入闭包”的多 Agent，避免 token 爆炸与信息交叉。

### 交付物
- 后端多 Agent 编排（Router → Controller/Guard → GM → 可选 Resolver → Tool）
- 每个 Agent 的输入/输出 schema（短 JSON/枚举/ID）

### 任务清单
- [ ] RouterAgent：识别本轮类型（推进/元问题/结算/冻结/总结）
- [ ] MainlineControllerAgent：里程碑门槛检查（未完成则只给补门槛选项）
- [ ] GuardAgent：现实护栏触发与“异常累计”复利升级（不对玩家报数）
- [ ] GM/NarratorAgent：输出玩家可见叙事 + 3–6 个选项（可附 `p_success`）
- [ ] 后端统一“最小输入闭包”组装：
  - 只喂：`campaign_id/session_id`、上次 `summary_json`、`milestone_id`、风险/信息档位、允许工具白名单
  - 禁止喂：历史叙事全文、文档数值
- [ ] 定义状态码体系（ID + 枚举）：
  - `scene_id / npc_id / event_id / clue_id`
  - `risk_tier / info_clarity_tier / milestone_id`
  - `abnormal_counter`（仅工具/文档存，LLM 只见“档位/信号”）

### DoD（验收）
- 每个 Agent 输入都可被限制在短 JSON（建议 <2KB，不含用户原话）；Agent 之间不传长文本；主线推进必须经过门槛检查。

---

## 里程碑 M2：压缩/总结机制（系统内置，非可选）

### 目标
- 每个 Session 结束必生成结构化 summary；下次仅凭 summary 即可继续（无历史叙事上下文）。

### 交付物
- `SessionSummary` JSON schema（facts/relations/irreversible/milestone/risk/open_questions）
- summary 写入工具（或写入统一 commit 工具）
- 后端强制 session_end 步骤

### 任务清单
- [ ] 定义 `SessionSummary` schema（条目数量/长度硬限制）
- [ ] SessionSummaryAgent：将本 Session 事件流压缩为 summary_json
- [ ] 工具写入：`session_summary_write`（写入文档 + 审计）
- [ ] “里程碑式压缩”落地：完成 Mx 时追加 `milestone_log`（机读 JSON，可选渲染 Markdown）
- [ ] “遗忘策略”硬编码：只长期保留公开事实/关系变化/不可逆后果

### DoD（验收）
- 任何重启只加载 summary_json 也能继续；summary 不随回合增长而膨胀（可控上限）。

---

## 里程碑 M3：工具扩展与稳定性（一次调用完成整回合）

### 目标
- 为满足“每次对话最多一次 tool_call”，将多步骤（掷骰/算 DC/写状态/写日志/写 summary）合并到一次工具调用中。

### 交付物
- `turn_commit`（建议）工具：一次调用完成读→算→写→日志→summary
- 并发控制与失败重试策略（幂等 + 版本号/事务）
- 观测性：request_id 全链路追踪

### 任务清单
- [ ] 设计 `turn_commit` 输入：
  - `campaign_id/session_id/player_id`
  - `milestone_id`、行动 `action_id`
  - `p_success`（由 GM 提供）
  - `check_type`（由外部系统决定能力需求）
  - `effects_intent[]`（例如 hp_reduce/status_apply）
- [ ] 工具内部集成概率裁定（若启用）：按 `../design/probabilistic_resolution_layer.md` 执行
- [ ] 并发写：乐观锁（version）或事务（SQLite）或文件锁（JSON 存储）
- [ ] 工具失败路径：可安全重放、不重复写、错误码统一
- [ ] 后端失败分支：LLM 输出不合规 → Repair 只修 JSON（不改语义）→ 重试

### DoD（验收）
- 一次 tool_call 即可完成“结算 + 状态写回 + 日志 + summary”；并发与重放安全；失败可定位。

---

## 需尽快确定的决策（否则会阻塞实现）
- [ ] 文档存储选型：仓库文件（JSON）/SQLite/Notion/其他（决定并发与事务方案）
- [ ] 协议字段统一：以 `say` 为准（如需兼容旧系统，再做 `narrative -> say` 映射；并确认是否允许同时返回工具结果给前端）
- [ ] “概率裁定”是否启用为默认：若默认启用，则必须先有 `turn_commit` 或等价一次调用工具
- [ ] 终局触发阈值与策略：异常累计达到阈值的结束条件（带离/冻结/封存丢失）如何落地成工具状态

---

## 建议的落地顺序（最省风险）
1) 先做 M0（单工具）跑通链路与幂等  
2) 再做 M2（summary 强制写入），确保 token 可控  
3) 再上 M1（多 Agent 拆分与门槛/护栏）  
4) 最后做 M3（turn_commit + 概率 + 并发稳定性）
