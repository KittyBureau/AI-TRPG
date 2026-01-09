# AI跑团：上下文功能（V0 全量发送）Codex 提示词（可直接执行）

> 目标：在 **FastAPI + Web 前端** 的现有项目中，加入“上下文（conversation history）+ 角色信息（character sheet）”的最小可用实现（V0：全量发送），并为后续“精简/压缩上下文”预留接口与 TODO。

---

## 0. 你必须先阅读的项目规范（强制）
1) 阅读仓库中的“规范文档主入口”（通常是 README 或 docs/index.md 或类似入口文件）。  
2) **在规范文档主入口中新增一条强制阅读要求**：实现/改动前，必须阅读 `docs/TODO_CONTEXT.md`（本次新增）。  
3) 任何新增文件与目录结构必须遵循现有规范（命名、位置、风格、日志等）。

---

## 1. 本次用户已确认的关键决策（不可擅改）

### 1.1 功能与会话范围
- **按功能模式拼接提示词**：当前只实现 “上下文 + 角色信息”；其他功能后续扩展。
- **各类功能独立**：不把多种功能放在同一个会话内，**暂不考虑 mode 切换**。
- 仍需 **预留 mode/上下文策略切换接口**：后续可能切换  
  - `full_context`（多信息上下文）  
  - `compact_context`（精简上下文）

### 1.2 system prompt 规则
- system prompt **作为每次请求 messages[0]** 注入（不存入历史，减小复杂度）。
- system prompt **每次从文件读取**（不固化在会话里）。

### 1.3 上下文内容（V0）
- 当前测试阶段：只发送 **历史文字信息**（user/assistant content）。
- 暂不做“手动删除消息”UI/接口；若需要，用户可直接编辑本地会话文件。

### 1.4 超长策略
- 超长（token 超限）时：**直接报错**（不自动裁剪、不自动摘要）。
- 允许记录 token 使用情况（用于后续优化）。

### 1.5 角色信息 / 规则 / 世界状态的注入策略
- 注入位置：**A：system 后、history 前**。
- 默认优先级（高到低）：  
  1) 角色卡（character sheet）  
  2) 规则文本（rules text）  
  3) 世界状态（world state）  
- 必须做成 **可配置/可修改**（先从本地 JSON 配置读取）。

### 1.6 存储与并发
- 存储形态：**一个会话一个文件**（A）。
- 写入：先写临时文件，再原子替换/并入。
- 并发：**不允许第二次 send 并发**；同一会话一次请求期间直接加锁（锁定）。

### 1.7 其他未明确项
- 其他内容你可自行选择最简方案，但必须：
  - 可运行
  - 可读
  - 易扩展
  - 不破坏既有代码

---

## 2. 需要你完成的开发任务（按最小改动推进）

### 2.1 新增/更新文档（必须）
1) 新增 `docs/TODO_CONTEXT.md`  
   - 写清楚后续要做的“上下文压缩/关键信息替代”的 TODO（见 4.1）。
   - 明确“哪些模块/函数未来要改”“什么是压缩版上下文”“验收标准”。

2) 修改“规范文档主入口”  
   - 新增一条：实现任何上下文相关功能前 **必须阅读** `docs/TODO_CONTEXT.md`。

> 注意：本次用户明确要求“标记上下文的代码，并在待办里写明后续压缩关键信息替代”，所以 `TODO_CONTEXT.md` 必须存在且被入口强制引用。

---

### 2.2 配置文件（本地 JSON；不做 UI）
1) 新增或扩展一个本地配置文件（例如 `data/config.json` 或 `data/llm_config.json`，以项目实际为准），包含：
   - `context_strategy`: `"full_context"`（默认）
   - `injection_priority`: `["character_sheet", "rules_text", "world_state"]`
   - 角色信息文件路径（或目录规则）
   - 规则文本文件路径（可选，先留空或占位）
   - 世界状态文件路径（可选，先留空或占位）
   - token 记录开关（例如 `log_tokens: true`）

2) system prompt 文件按功能模式拆分（先只实现当前用到的一个/两个）：
   - 例如：`prompts/system/chat.txt` 或 `prompts/system/context_full.txt`
   - 由后端按“功能模式”读取并注入为 messages[0]

---

### 2.3 后端：会话与消息存储（最简）
1) 设计会话文件结构（JSON），建议：
   - `conversation_id`
   - `created_at`, `updated_at`
   - `messages`: [{role, content, created_at, meta?}]
   - `meta`: { model, base_url, token_usage? }

2) 文件组织：
   - 建议 `storage/conversations/{conversation_id}.json`
   - 临时文件：`{conversation_id}.json.tmp`（写完校验后替换）

3) 并发锁：
   - 同一 `conversation_id` 的 send 期间锁定。
   - 如果再次请求，返回明确错误（HTTP 409 或自定义错误码）。

---

### 2.4 后端：Chat API（V0 全量发送）
新增 `POST /api/chat/send`（或按项目现有路由风格放置）：

**输入**
- `conversation_id`：可选；为空则创建新会话
- `user_text`：必填
- `mode`：可选（先保留接口字段，但默认固定一个）
- `context_strategy`：可选（默认读取配置 `full_context`）
- （模型选择/URL/key 等）按你项目现有“多 key 管理”方案引用（不使用环境变量）

**处理流程（固定管线）**
1) 读取配置（json）
2) 若无 conversation：创建文件（空 messages）
3) 加锁（per conversation_id）
4) 读取 system prompt 文件 -> 构造 messages[0]
5) 读取会话历史 messages（只取 user/assistant 的 content）
6) 读取“注入块”（只实现角色信息；规则/世界状态先做占位接口）  
   - 按优先级拼接成 `extra_context_blocks`
   - 注入位置：system 后、history 前
7) 拼请求 messages = [system] + extra_blocks_as_messages + history + [current user]
8) 调 OpenAI 兼容接口（你项目已有封装则复用）
9) 将本次 user 与 assistant reply 追加到会话文件（原子写入）
10) 记录 token 用量（如响应提供 usage）到 message.meta 或会话 meta
11) 释放锁并返回

**输出**
- `conversation_id`
- `assistant_text`
- 可选：`token_usage`（若可得）

---

## 3. 标记“未来要压缩上下文”的代码位置（必须）
你需要在代码中用清晰注释标记未来要替换为“关键信息/摘要”的位置，例如：

- `# TODO(context): replace full history with compact key facts per TODO_CONTEXT.md`
- `# TODO(context): implement compact_context strategy`

这些 TODO 必须与 `docs/TODO_CONTEXT.md` 中的条目一一对应（能互相定位）。

---

## 4. docs/TODO_CONTEXT.md 必须包含的内容（模板要求）

### 4.1 上下文压缩（关键信息替代）计划
至少包含以下 TODO（可按项目实际补充）：

- [ ] `compact_context` 策略：只保留关键信息（角色卡要点 + 最近 N 轮对话 + 世界状态摘要）
- [ ] 自动摘要触发：当历史超过 token_budget 的 X% 时生成摘要（V1/V2）
- [ ] 关键事实提取：从历史中提取“人物关系、目标、地点、道具、任务进度”（结构化 JSON）
- [ ] “固定信息 pin”：角色卡/规则的关键条目永不裁剪
- [ ] 可配置优先级与注入块最大长度
- [ ] token 预算估算与可视化（先日志，后 UI）
- [ ] 回归测试：相同输入在 full_context/compact_context 下输出差异可控

### 4.2 验收标准
- V0：全量上下文可用；角色信息注入可用；超长直接报错；并发锁生效；会话文件可恢复。
- V1：compact_context 可切换；关键事实替代生效；token 成本下降且不明显跑偏。

---

## 5. 实现约束（避免返工）
- 不新增交互式配置 UI；所有配置写在本地 JSON。
- 不使用环境变量读取 API key；只走你现有“加密 key 文件/多 key 管理”读取逻辑。
- 新增代码尽量模块化：  
  - `services/context_builder.py`（或类似）负责拼 messages  
  - `storage/conversations.py` 负责读写与锁  
  - `routes/chat.py` 提供接口
- 日志：避免记录完整敏感内容；默认只记录元信息（长度、token、耗时）。

---

## 6. 交付物清单（你完成后必须自检）
- [ ] 新增 `docs/TODO_CONTEXT.md`
- [ ] 规范文档主入口已添加“必须阅读 TODO_CONTEXT.md”
- [ ] 新增/更新本地 json 配置：包含 context_strategy 与 injection_priority
- [ ] 会话文件存储：一会话一文件 + 临时文件原子写
- [ ] per-conversation 锁：二次 send 返回明确错误
- [ ] /api/chat/send 跑通：system + 角色信息注入 + 历史 + 当前输入
- [ ] token usage 记录（可得则记录，不可得不强求）
- [ ] 代码里已标记 TODO(context) 注释并能对应到 TODO 文档

---

## 7. 开始执行前的仓库扫描要求（防止放错位置）
- 先在仓库中搜索：
  - 已有 routes 结构（例如 `backend/routes` 或 `backend/routes`）
  - 已有 storage/services 目录命名方式
  - 规范入口文件路径
- 避免改动旧代码：优先“新增文件 + 轻量接线”方式接入。

---

> 执行方式：按上述清单逐项提交；每个关键文件改动都写清楚目的与后续扩展点。不要做超出范围的优化。
