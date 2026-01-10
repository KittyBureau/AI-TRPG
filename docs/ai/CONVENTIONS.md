# 约定

## 目录约定
- `backend/app/` - FastAPI 入口与路由装配。
- `backend/services/` - 业务逻辑与工具行为。
- `backend/storage/worlds/` - 版本化的静态世界数据。
- `backend/storage/runs/` - 动态状态与事实（允许样例数据）。
- `frontend/public/` - 静态界面资源。
- `docs/ai/` - 人工智能索引系统与仓库级标准。
- `docs/ai-trpg/` - 领域设计/规格文档。

git 忽略（本地专用）目录：
- `data/`
- `backend/data/`
- `backend/logs/`

## 命名约定
- Python 模块/函数：`snake_case`。
- Python 类：`PascalCase`。
- JSON 文件名：`snake_case`（示例：`sample_world.json`）。
- ID 前缀：`loc_*`、`pc_*`（按需扩展）。
- 移动路径 `path_id`：`loc_a->loc_b->loc_c`（稳定签名）。

## 日志与错误处理
- 服务层抛出领域异常；API 层映射为 JSON 错误。
- 错误响应格式：`{"status":"ERROR","message":"..."}`。
- 日志框架：???（默认：Python `logging`，模块级 logger）。

## 配置与环境
- 必需：`~/.ai-trpg/secrets.enc`（加密）与 `~/.ai-trpg/config.json`。
- 其他配置文件：???（默认：用户目录或 `backend/storage/` 下的 JSON 模板）。

## 数据持久化规则
- 版本化样例与夹具放在 `backend/storage/`。
- 运行期输出放在 git 忽略目录。
- 不提交密钥或 `.env` 文件。`secrets.enc` 只保留本地。
