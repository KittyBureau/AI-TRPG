# 架构

## 概览
- 运行代码位于仓库根目录（FastAPI 后端 + 静态前端）。
- 设计/规格文档位于 `docs/`。

## 当前分层
- API 层：`backend/app/main.py`（FastAPI 路由与请求模型）。
- 服务层：`backend/services/`
  - `llm_client.py`（大语言模型调用 + JSON 校验）
  - `character_service.py`（角色生成/保存）
  - `world_movement.py`（移动路径 + 移动结算）
- 存储（JSON 文件）：`backend/storage/`
  - `worlds/`（静态世界）
  - `runs/`（动态状态）
- 运行期数据输出：`data/characters/`（git 忽略）。
- 前端：`frontend/public/`（静态 HTML/JS/CSS）。
- 测试：`backend/tests/`（占位；测试运行器 ???，默认：pytest）。

## 边界
- API 层应保持轻薄；将逻辑下沉到服务层，并把错误映射为 JSON 响应。
- 服务层避免依赖 FastAPI，返回纯数据或抛出领域错误。
- 存储访问通过服务层；前端不直接读取存储。
- git 忽略数据目录仅为本地运行期使用，不属于版本化样例。

## 外部依赖
- FastAPI + Pydantic 用于 HTTP 层。
- httpx 用于大语言模型调用。

## 待确认事项（???）
- 存储抽象（JSON 与 数据库）与锁策略。
- 测试运行器与持续集成流程。
