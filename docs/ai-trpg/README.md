# AI 跑团文档索引（docs/ai-trpg）

本目录整理了一个「AI 叙事 + 工具结算（读写文档）+ Python 后端编排 + 多 Agent 分工（可选）」的设计与样例材料，目标是低 token、强门槛、可压缩重启。

## 推荐阅读顺序
1. 框架总览：`docs/ai-trpg/design/framework.md`
2. 多 Agent 任务提示词（投喂 Codex）：`docs/ai-trpg/prompts/multi_agent_task_prompt.md`
3. 应用级设计文档（Python 后端 + Web 前端）：`docs/ai-trpg/specs/tool_spec.md`
4. 主线门槛与偏离矫正：`docs/ai-trpg/design/mainline_milestones.md`
5. 主线保护与复利式风险：`docs/ai-trpg/design/mainline_protection_mechanism.md`
6. 现实护栏库（Guards）：`docs/ai-trpg/design/reality_guards.md`
7. 可选 D20 概率裁定层：`docs/ai-trpg/design/probabilistic_resolution_layer.md`


## 设计思路分块（快速定位）
- 总览与目标：`docs/ai-trpg/design/framework.md`
- 多Agent分工与提示词入口：`docs/ai-trpg/prompts/multi_agent_task_prompt.md`
- 工具协议与读写闭环：`docs/ai-trpg/specs/tool_spec.md`
- 主线门槛与偏离纠正：`docs/ai-trpg/design/mainline_milestones.md`
- 主线保护与复利式风险：`docs/ai-trpg/design/mainline_protection_mechanism.md`
- 现实护栏库（Guards）：`docs/ai-trpg/design/reality_guards.md`
- 概率裁定层（D20）：`docs/ai-trpg/design/probabilistic_resolution_layer.md`
- 跑团记录与测试样例：`docs/ai-trpg/runs/2026-01-06_trpg_test/internal_notes.md`，`docs/ai-trpg/runs/2026-01-06_trpg_test/milestone_log.md`，`docs/ai-trpg/prompts/trpg_test_prompt.md`
- 工程待办与里程碑拆分：`docs/ai-trpg/project/todo.md`
- 跨工具协作流程：`docs/Cursor_ChatGPT_Codex_工作流.md`

## 目录结构
```text
docs/ai-trpg/
  prompts/                # 可直接投喂的单文件提示词
  specs/                  # 工具/协议规范（工具负责读→算→写→日志）
  design/                 # 机制与架构设计（里程碑、护栏、概率层等）
  project/                # 工程落地待办与里程碑拆分
  runs/                   # 跑团过程记录（内部笔记、里程碑压缩示例）
```

## 关键约束（项目共识）
- **一次对话最多一次 tool_call**：多步骤结算应合并为一次提交工具（建议 `turn_commit`）。
- **AI 不读取/不缓存文档数值**：LLM 只接收 summary/ID/枚举；真实数值由工具从文档读取计算。
- **Session Summary 是系统内置步骤**：每个 Session 结束必须写入结构化 summary，供下次重启。
- **主线里程碑硬门槛**：未完成当前里程碑，不进入下一步主线内容；偏离会被现实护栏矫正回流。

## 工程待办
- 待办清单：`docs/ai-trpg/project/todo.md`

## 跑团记录示例
- 内部笔记：`docs/ai-trpg/runs/2026-01-06_trpg_test/internal_notes.md`
- 里程碑压缩：`docs/ai-trpg/runs/2026-01-06_trpg_test/milestone_log.md`
- 单文件跑团测试提示词：`docs/ai-trpg/prompts/trpg_test_prompt.md`
