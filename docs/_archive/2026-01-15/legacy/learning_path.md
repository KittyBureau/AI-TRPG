# 项目学习流程（Human-only）

> 说明：本文档面向人类读者，用于从零开始理解与上手本仓库。  
> AI agent 默认不应加载本文档（避免无关上下文与 token 浪费）；如明确需要“面向人类的教学/引导”，再按需引用。

## 0) 学习目标（先定边界）
- 目标 A：能跑起来仓库根目录下的最小原型（FastAPI + 静态前端），并能调用 `/api/chat/send`。
- 目标 B：能理解“路由决策 → context_profile → messages 拼装 → LLM 调用 → 会话落盘”的管线。
- 目标 C：能按规范改动：优先配置驱动，避免把业务分支堆进 `context_builder`。

## 1) 先看全局入口（10 分钟内）
1. `README.md`：仓库定位、启动方式、必读入口。
2. `backend/README.md`：可运行原型结构与关键模块位置。
3. `docs/reviews/CODE_REVIEW_2026-01-09.md`：当前阶段的功能级快照（用于对齐“现在有什么”）。

## 2) 再读规范与索引（建立共同语言）
按 `docs/_archive/2026-01-15/ai/AI_INDEX.md` 的“Core docs”顺序阅读：
1. `docs/_archive/2026-01-15/ai/CONVENTIONS.md`：目录/命名/数据落地规则（尤其是 gitignored 目录与存储分层）。
2. `docs/_archive/2026-01-15/ai/ARCHITECTURE.md`：当前分层与边界（API 薄层、services 为主）。
3. `docs/_archive/2026-01-15/ai/DECISIONS.md`：默认决策与理由（便于理解为何这样组织代码）。
4. `docs/_archive/2026-01-15/ai/CHECKLIST.md`：提交前检查（格式/静态检查/测试）。
5. `docs/_archive/2026-01-15/ai/CHANGELOG_AI.md`：文档体系的演进记录（用于理解最近变更）。

## 3) 聚焦“上下文与路由”主线（建议先走这条）
1. `docs/_archive/2026-01-15/todo_context.md`：上下文压缩与关键事实替代的待办与验收口径（任何 context 相关改动前必读）。
2. `docs/03_reference/design/dialog_routing.md`：路由协议、block 枚举、context_profile 与 system prompt 映射（规格来源）。
3. `docs/_archive/2026-01-15/legacy/dialog_routing_test_method.md`：路由测试方法（Method A/B）与 UTF-8 请求注意事项。
4. `backend/storage/config_template.json`：可复制的配置模板（profiles/routes/paths）。

## 4) 跑起来（先能工作，再谈优化）
在仓库根目录：
1. 创建并激活虚拟环境：`python -m venv .venv`，`.\\.venv\\Scripts\\Activate.ps1`
2. 安装依赖：`python -m pip install -r backend/requirements.txt`
3. 配置 secrets + config：`python -m backend.secrets.cli`
   - 生成 `%USERPROFILE%\\.ai-trpg\\secrets.enc` 与 `%USERPROFILE%\\.ai-trpg\\config.json`
   - 建议先从 `backend/storage/config_template.json` 复制 context 配置段到 `config.json`
4. 启动服务：`python -m uvicorn backend.app.main:app --reload`
5. 验证接口：按 `docs/_archive/2026-01-15/legacy/dialog_routing_test_method.md` 的 Method B 请求 `/api/chat/send`

## 5) 读代码（只看“职责”，不逐行抠实现）
建议按“入口 → 管线 → 配置/存储 → LLM → 安全”顺序走读：
1. `backend/app/main.py`：HTTP 路由与请求模型（API 薄层）。
2. `backend/services/chat_service.py`：对话请求主流程（锁、路由、构造 messages、调用 LLM、落盘）。
3. `backend/services/dialog_router.py`：路由决策对象产出（规则：route 不在 builder 内推断）。
4. `backend/services/context_config.py`：配置解析（profiles/routes/paths/guards）。
5. `backend/services/context_builder.py`：按 profile 拼装 messages（full_context/compact_context）。
6. `backend/services/conversation_store.py`：会话文件格式、原子写入、并发锁。
7. `backend/services/llm_client.py`：OpenAI-compatible 调用与 JSON/usage 处理。
8. `backend/secrets/*`：本地加密 secrets、明文 config、CLI 写入与 provider 路由。

## 6) 做第一处改动（推荐流程）
1. 先改配置与文档（对齐规格）：`docs/03_reference/design/dialog_routing.md` / `docs/_archive/2026-01-15/todo_context.md`
2. 再改 `backend/storage/config_template.json`（提供可复制模板）
3. 再改代码（小步提交，避免重构）：优先新增模块或扩展配置解析
4. 用 `docs/_archive/2026-01-15/legacy/dialog_routing_test_method.md` 复测：
   - Method A：离线检查 messages 拼装
   - Method B：真实 API 调用与会话落盘字段检查

## 7) 需要深入“AI-TRPG 设计”的读法（可选分支）
1. `docs/03_reference/ai-trpg/README.md`：设计文档索引与关键约束。
2. `docs/03_reference/ai-trpg/design/framework.md`：框架与多 Agent 分工思想。
3. `docs/03_reference/ai-trpg/specs/tool_spec.md`：工具协议与“权威状态不回灌 LLM”的边界。
4. `docs/03_reference/ai-trpg/project/todo.md`：工程里程碑（M0–M3）与 DoD。

## 8) 常见坑位（从仓库现状反推）
- 配置文件路径在用户目录：`%USERPROFILE%\\.ai-trpg\\config.json`，不在仓库内。
- PowerShell 直接 `Invoke-RestMethod -Body $jsonString` 可能导致中文变 `?`，按测试文档的 UTF-8 safe 写法发送。
- `full_context` 默认会拼全量历史；若要“只读 rules_text / 不带历史”，需要 profile 使用 `compact_context` 且排除 `recent_turns/key_facts`。
