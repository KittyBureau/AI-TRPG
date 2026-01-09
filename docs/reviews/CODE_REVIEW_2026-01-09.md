# CODE_REVIEW_2026-01-09

## 1. 项目定位与目标
- 本仓库以文档为主，覆盖 AI 跑团的设计规范、提示词和工程待办，同时提供可运行的 FastAPI + 静态前端原型。
- 设计目标强调低 token、工具读写权威状态、一次对话最多一次工具调用、会话可压缩重启等约束。
- 运行代码聚焦最小闭环：对话、角色生成、世界移动工具以及本地存储与配置管理。
- 目录约定与分层规范通过 docs/ai 系列文档固化，后端逻辑集中在 services 层。

## 2. 当前已实现的核心功能（V0 视角）
- FastAPI 后端提供对话入口 `/turn`、聊天上下文 `/api/chat/send`、角色生成 `/api/characters/*`、世界移动 `/api/world/*` 等接口，并提供静态前端入口页。
- LLM 调用使用 OpenAI-compatible 接口，具备 JSON 结构校验与错误处理，支持记录 token 使用情况。
- 会话持久化采用每会话一文件（JSON），支持原子写入与会话级并发锁。
- 上下文构建支持 system prompt + 注入块（角色卡/规则/世界状态等）+ 历史消息拼接，并可按 profile 选择 full_context / compact_context。
- 对话路由已落地：通过 dialog_type/variant 决定 context_profile，路由决策写入会话 meta。
- 角色生成具备 JSON schema 解析、ID/名称清洗、重名冲突处理与本地保存。
- 世界移动实现路径枚举与移动结算，基于样例世界与状态文件，附带风险等级与事实记录。
- 本地密钥与配置管理已落地：加密 secrets + 明文 config + CLI 写入与路由配置。

## 3. 会话 / 上下文系统的功能性说明
- 会话以 `conversation_id` 作为索引，存储于 `codes/backend/data/conversations/`，记录创建/更新时间与消息列表。
- 并发控制采用进程内锁：同一会话在发送期间加锁，防止并行写入。
- `context_strategy` 支持 `full_context` / `compact_context` / `auto`（profile 默认可覆盖）；compact 模式按 summary/key_facts/recent_turns 组装。
- system prompt 支持按 `dialog_type + response_style` 映射文件，或显式 `mode` 指定。
- 注入块顺序与路径由 config.json 控制，支持文件或目录读取，未配置项自动跳过；rules_text_path 可独立注入规则文本。
- persona lock 规则在构建与回包阶段均有约束：用户提示触发时注入限制提示，输出检测到身份漂移时改写为固定 GM 响应。

## 4. 角色与身份设计（GM / PC / NPC 的职责边界）
- 系统 prompt 明确 GM 身份不可切换，禁止以 PC/NPC 身份发言，NPC 台词仅允许带标签输出。
- 角色卡注入以“参考资料”形式给出，明确不代表助手身份，降低身份混淆风险。
- 聊天服务对身份漂移进行模式检测并覆盖输出，作为运行时的防护兜底。
- 设计文档进一步定义 GM/State Tracker/Guard 等角色职责与边界，但当前实现仍以单 GM 输出为主。

## 5. 配置与可扩展点概览
- 配置与密钥集中在用户目录（`%USERPROFILE%\.ai-trpg\`），支持 provider 路由与多模型配置。
- `codes/backend/storage/config_template.json` 提供上下文策略、注入优先级、路由表与 profiles 模板，便于实例化。
- 后端预留 `api/agents/tools/core` 等目录，便于后续扩展多 Agent 编排与工具服务。
- 世界移动模块支持自定义 world/state 路径与风险过滤，路径 ID 采用稳定签名。
- 前端为最小静态页面，当前仅提供对话与角色生成入口，便于替换为更完整的 UI。
- 文档层面已给出多 Agent 架构、里程碑、护栏与概率裁定等设计扩展基线。
- 已补充路由规格与测试方法文档：`docs/design/dialog_routing.md`、`docs/testing/dialog_routing_test_method.md`。

## 6. 当前刻意未实现或被延后的能力
- 自动摘要触发、关键事实抽取、固定信息 pin、token 预算估算等仍在 TODO 中，尚未落地。
- 统一的 `/session/new`、`/turn` 强校验协议、`/state`、`/logs`、工具白名单与一次 tool_call 机制仍处于设计阶段。
- 多 Agent 路由、主线门槛控制、护栏/风险累积与 SummaryAgent 写回未在运行代码中实现。
- `state_patch` / `turn_commit` 等一次性结算工具、幂等审计、并发写冲突处理仍待实施。
- 存储抽象（JSON vs SQLite）与测试/CI 方案在架构文档中标记为待确认项。

## 7. 后续演进方向（基于已有 TODO 文档）
- 依据 `docs/TODO_CONTEXT.md` 推进关键事实抽取、自动摘要与回归验证，补齐上下文压缩链路。
- 依据 `docs/ai-trpg/project/todo.md` 完成 M0–M3 里程碑：严格 TurnOutput JSON、工具白名单、Summary 写回、单次工具提交与并发稳定性。
- 引入 Router/Controller/Guard/GM/Summary 等多 Agent 角色，保证最小输入闭包与里程碑门槛机制。
- 落地 `state_patch` / `summary_writeback` 工具与审计日志，确保“AI 不读权威数值”的边界可执行。
- 明确存储选型与锁策略，建立基础测试与校验流程，支撑后续扩展与回归。
