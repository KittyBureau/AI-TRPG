# AI-TRPG 项目进度同步（给网页端 ChatGPT）

## 项目定位
- 以文档为主，提供可运行的 FastAPI 后端 + 静态前端原型。
- 目标是低 token、工具读写权威状态、一次对话最多一次工具调用、会话可压缩重启。

## 当前已实现（可运行能力）
- 后端接口：对话 `/turn`、聊天上下文 `/api/chat/send`、角色生成 `/api/characters/*`、世界移动 `/api/world/*`。
- LLM 调用：OpenAI 兼容接口，带 JSON 结构校验、错误处理、token 统计。
- 会话存储：每会话一 JSON 文件，原子写入 + 会话级并发锁。
- 上下文构建：system prompt + 注入块（角色卡/规则/世界状态等）+ 历史消息拼接；支持 full_context / compact_context / profile。
- 对话路由：dialog_type/variant -> context_profile，路由结果写入会话 meta。
- 角色生成：JSON 解析、ID/名称清洗、重名冲突处理、本地保存。
- 世界移动：路径枚举 + 移动结算，基于样例世界与状态文件。
- 本地密钥与配置：加密 secrets + 明文 config + CLI 写入与路由配置。

## 项目结构要点
- 运行代码：`backend/`（FastAPI），静态前端：`frontend/public/`。
- 版本化数据：`backend/storage/`；运行期数据：`data/`（gitignored）。
- 配置与密钥：`~/.ai-trpg/config.json`、`~/.ai-trpg/secrets.enc`。

## 路由/上下文测试方法（已有文档）
- `docs/testing/dialog_routing_test_method.md` 提供离线组装与 API 级验证步骤。

## 近期文档修正
- 已清理文档中的硬编码绝对路径示例，统一使用可移植的占位或 `~/.ai-trpg/`。

## 仍待实现（TODO_CONTEXT）
- 自动摘要触发（token 超限滚动摘要）。
- 关键事实抽取为结构化 JSON。
- 固定信息 pin 机制（关键角色/规则不裁剪）。
- 注入块优先级与长度上限可配置。
- token 预算估算与可见性（先日志后 UI）。
- full_context 与 compact_context 的回归一致性检查。
- 角色身份混淆防护与 GM persona lock 强化。

## 备注
如需我继续推进上述 TODO 的具体实现，请指定优先顺序或目标范围。
