# Codex 参考提示词：两阶段回合（Plan→Apply→Narrate）+ 记录 TODO

> **强制暂停规则（必须遵守）**
> - 若发现本文要求与仓库当前实现/数据模型/测试/文档不一致或存在歧义：**立即停止并向用户确认**。
> - 禁止顺手重构；仅做本文要求的最小改动。
> - 本任务当前**不要求立刻完成实现**：用户暂无时间改代码。你需要先把任务内容写入项目 TODO（见第 1 节），并在提交信息中注明。

---

## 0. 背景与目标

当前存在“口头移动”问题：LLM 在 `assistant_text` 描述已移动，但未发起 `move` tool_call；由于已停用叙事关键词冲突检测，后端不会拦截，导致叙事与 `positions` 不一致。

目标：实现**两阶段回合**（也可称 Plan/Apply/Narrate），让叙事永远基于已执行的权威状态：
- **Plan**：LLM 只产出 `tool_calls`（不写完成时态叙事）
- **Apply**：后端执行工具，更新权威状态，记录 applied_actions
- **Narrate**：第二次调用 LLM，只写叙事，不再执行工具

并为未来拆分“tool-call 轻量模型 vs 主叙事模型”留接口。

---

## 1. 开工前：把任务写入 TODO（必须先做）

在项目中找到现有的 TODO 记录方式（例如 `TODO.md`、`docs/TODO.md`、`docs/99_todo.md` 等）。
若找不到统一 TODO 文件：创建 `TODO.md` 于仓库根目录（最小内容即可）。

新增条目（建议原文保留）：

### [TODO] Two-stage Turn Pipeline (Plan → Apply → Narrate)
- Problem: narrative can claim movement/state change without move tool_call, causing state drift.
- Solution: split each /api/chat/turn into:
  1) Plan LLM call: output only tool_calls (no completed narration)
  2) Apply tools: execute tool_calls, update campaign, write applied_actions
  3) Narrate LLM call: output final assistant_text based on tool results + updated state (tool_calls must be empty)
- Add config hooks for future separation:
  - TOOL_LLM_PROFILE / NARRATE_LLM_PROFILE (or similar)
  - Allow using a lighter model for Plan phase later
- Acceptance: no “oral movement”; narration always matches positions.

提交该 TODO 变更（单独 commit 或与后续实现同 commit 皆可）。

> **完成 TODO 写入后：如果用户没有回复“继续实现”，你应停止，不进行代码改动。**

---

## 2. 实现方案（用户确认采用推荐默认值）

### 2.1 采用变体 A：两次 LLM 调用（最稳）
- LLM#1：Plan（仅 tool_calls）
- 工具执行：Apply
- LLM#2：Narrate（仅 assistant_text，tool_calls 必须为空）

### 2.2 Plan 阶段输出协议（严格）
- 输出 JSON 键仍为：`assistant_text`, `dialog_type`, `tool_calls`
- 但要求：
  - `assistant_text` 必须为空字符串或非常简短的 plan_note（不含任何完成时态叙事）
  - `dialog_type` 可固定为 `"planning"`（若你的 DIALOG_TYPES 不含 planning，则保持现状但不要影响解析；如不确定，暂停确认）
  - `tool_calls`：由 LLM 决策产生；允许为空（表示无需工具）
- 明确在 system prompt 中写：
  - “In PLAN mode: do NOT narrate outcomes. Only propose tool_calls.”
  - “Never describe completed movement/location change in PLAN mode.”

### 2.3 Apply 阶段（复用既有）
- 复用现有 `tool_executor.py` 执行逻辑（包括 `move`、`move_options`）
- 工具执行结果整理为 `tool_results`：每个 tool_call 对应 success/failed + payload/reason
- 更新 campaign 权威状态并写审计（沿用现有 applied_actions 结构，不强制扩展）

### 2.4 Narrate 阶段输出协议（严格）
- 再次调用 LLM，提供：
  - 原用户输入（可选）
  - tool_results（必须）
  - 更新后的 state_summary/positions（必须）
- 要求：
  - `tool_calls` 必须是空数组
  - 叙事必须以工具结果为准：
    - move 成功：描述新位置
    - move 失败：解释失败原因，给出下一步建议（可提示使用 move_options）

---

## 3. 代码改动建议落点（仅供实现时参考）

> 若你现在只被要求“写 TODO”，到此为止。只有用户回复“继续实现”才进入本节。

- `turn_service.py`（或等价入口）：
  - 将当前单次 LLM 调用改为 Plan→Apply→Narrate 两次调用
  - 增加一个“mode”或“phase”注入到 system prompt（PLAN/NARRATE）
- `system prompt builder`：
  - 支持按 phase 输出不同规则（PLAN 禁止叙事，NARRATE 禁止 tool_calls）
- 保留未来扩展接口（不必现在启用）：
  - `PLAN_MODEL_PROFILE` / `NARRATE_MODEL_PROFILE` 配置项（或同义）
  - 默认两阶段都用当前 selected profile（用户后续会改为轻量模型做 Plan）

---

## 4. 测试与验收（实现阶段）

- 回归：`python -m pytest -q`
- 新增（如你认为必要且不引发争议）：
  - “Plan 阶段 assistant_text 不得包含完成时态移动叙事” 的单测（可只做 smoke）
  - “Narrate 阶段 tool_calls 必须为空” 的单测

验收关键点：
- 用户输入“OK, I want to move to the side room.”
  - Plan：出现 move 或 move_options 的 tool_call
  - Apply：positions 变化（若 move 成功）
  - Narrate：叙事与 positions 一致，且 tool_calls 为空

---

## 5. 交付要求（现在阶段）

- **必须**先把第 1 节 TODO 写入并提交。
- 若用户未明确要求“继续实现”：
  - 停止在 TODO 提交，不做代码改动。
- 若用户回复“继续实现”：
  - 再进入实现阶段，并确保全量 pytest 通过。
