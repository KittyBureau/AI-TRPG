# External Resources Management Roadmap

目的：
逐步实现“外部资源集中管理”，将频繁变更的内容（prompt、flow、schema、策略等）
从代码中解耦，使系统具备：

- 版本化
- 可回滚
- 可观测
- 可配置

该文档为长期 TODO 规划，不代表当前系统已实现。

---

# Phase 0 — 基础资源结构

目标：建立统一资源目录与注册表。

TODO:

- [ ] 创建统一资源目录 `resources/`
- [ ] 子目录规划：
  - `resources/prompts/`
  - `resources/flows/`
  - `resources/schemas/`
  - `resources/templates/`
  - `resources/fixtures/`（可选）
- [ ] 新增资源注册表 `resources/manifest.json`
- [ ] manifest 字段设计：
  - type
  - name
  - version
  - path
  - hash
  - enabled
- [ ] 设计资源版本切换机制（stable / experimental）

---

# Phase 1 — Prompt 与代码解耦

目标：将 prompt 从代码中抽离。

TODO:

- [ ] 抽取所有 prompt 到 `resources/prompts/`
- [ ] 代码通过 manifest 加载 prompt
- [ ] 支持 prompt 版本管理
- [ ] 在 turn debug 输出中记录：
  - prompt_version
  - prompt_hash

---

# Phase 1 — Flow / 行为策略外置

目标：将系统行为流程配置化。

TODO:

- [ ] 定义 flow 配置格式：

resources/flows/<flow_id>.json

包含：

- steps
- step inputs
- step outputs
- retry policy
- expected fields validation

- [ ] 将核心流程迁移为 flow：

示例：

character_generate → adopt → party_load → select_active → turn

- [ ] 运行时从 flow 配置驱动

---

# Phase 1 — Tool Permission 与 Retry 策略

目标：避免 tool 行为散落在代码中。

TODO:

- [ ] tool allowlist 配置化
- [ ] 不同 dialog / flow step 使用不同 tool policy
- [ ] conflict / retry 策略模板化

示例：

invalid_args
missing_fields
tool_not_allowed

- [ ] turn debug 输出记录：
  - tool policy version
  - allowed tools

---

# Phase 1 — Schema 与 Template 集中

目标：统一数据契约。

TODO:

- [ ] 集中 JSON schema：

resources/schemas/

包括：

- CharacterFact
- Campaign
- World
- ToolCall

- [ ] 集中 templates：

resources/templates/

包括：

- campaign stub
- world stub
- character stub

- [ ] normalize / clean 规则逐步配置化

---

# Phase 2 — 前端资源集中

目标：避免 UI 文案和调试逻辑散落。

TODO:

- [ ] 集中 UI 文案：

frontend/resources/strings.json

- [ ] 集中 debug 展示模板：

frontend/resources/debug_views.json

- [ ] 前端 panel 统一引用这些资源

---

# Phase 2 — 测试与回归资源化

目标：可复现系统行为。

TODO:

- [ ] 建立测试用例目录：

docs/02_guides/testing/cases/

- [ ] fixtures：

resources/fixtures/

- [ ] golden outputs：

backend/tests/golden/

- [ ] turn transcript 录制与回放机制（后续）

---

# Phase 2 — 资源版本化与回滚

TODO:

- [ ] 每个资源带 version
- [ ] manifest 控制 active version
- [ ] 记录资源 changelog：

resources/CHANGELOG.md

---

# Phase 2 — 可观测性

目标：使每次运行可复现。

TODO:

turn debug 输出记录：

- flow_id
- flow_version
- prompt_version
- schema_version

---

# Long Term

未来可能扩展：

- campaign 级资源覆盖
- prompt A/B testing
- 自动化回归测试
- resource hot reload

---

# Implemented Snapshot (Minimal, 2026-03)

Current flow externalization is metadata-only (non-executing):

- `resources/manifest.json` now supports `flows` entries.
- Example flow file: `resources/flows/play_turn_basic_v1.json`
- Runtime execution path is unchanged; flow is loaded for trace/observability only.

Minimal flow JSON shape in use:

```json
{
  "id": "play_turn_basic",
  "version": "v1",
  "steps": [
    { "id": "prompt_render", "kind": "prompt_render" },
    { "id": "chat_turn", "kind": "chat_turn" },
    { "id": "apply_tools", "kind": "apply_tools" },
    { "id": "state_refresh", "kind": "state_refresh" }
  ]
}
```

---
