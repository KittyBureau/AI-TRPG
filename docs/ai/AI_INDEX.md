# 人工智能索引

本目录提供人工智能相关文档与编码规范的最小索引。

## 核心文档
- `docs/ai/CONVENTIONS.md` - 目录、命名、日志、配置与数据放置规则。
- `docs/ai/ARCHITECTURE.md` - 当前分层与模块边界。
- `docs/ai/DECISIONS.md` - 默认决策（含理由）。
- `docs/ai/CHECKLIST.md` - 提交前检查（格式化/静态检查/类型/测试）。
- `docs/ai/CHANGELOG_AI.md` - 人工智能文档变更日志。

## 项目文档
- `docs/ai-trpg/README.md` - AI-TRPG 文档索引。
- `docs/ai-trpg/specs/tool_spec.md` - 工具协议与后端设计。
- `docs/ai-trpg/specs/world_space_and_movement_spec.md` - 移动系统规格。
- `docs/ai-trpg/project/world_space_and_movement_implementation.md` - 实现说明。

## 设计文档
- `docs/design/dialog_routing.md` - 对话路由与上下文配置说明。

## 测试文档
- `docs/testing/dialog_routing_test_method.md` - 对话路由测试流程。

## 提示词
- `docs/ai/CODE_REVIEW_PROMPT.md` - 生成周期性代码评审文档的 Codex 提示词。

## 更新规则
- 保持条目简短稳定；细节放到目标文档中扩展。
- 上下文相关工作前必须阅读：`docs/TODO_CONTEXT.md`。
- `docs/human/` 为人类专用入门文档（例如 `docs/human/LEARNING_PATH.md`），除非明确要求，否则应跳过。
- 如有不确定项，标记为 "???" 并给出默认方案。
