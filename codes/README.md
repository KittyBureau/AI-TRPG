# codes 目录说明（预留结构）

> 说明：已在 `codes/` 下预留后端与前端的目录结构；**不移动任何现有代码**。  
> 现有文件仍保留在：`codes/backend/*.py` 与 `codes/frontend/index.html|app.js|style.css`。

## 目录结构（预留）
```text
codes/
  backend/
    app/            # 应用入口/依赖注入/生命周期
    api/            # 路由层（HTTP API）
    agents/         # 多 Agent/LLM 调度与策略
    core/           # 配置、常量、错误码、权限
    services/       # 业务服务层（turn/session/state）
    tools/          # 工具调用层（state_patch/summary_writeback 等）
    storage/        # 存储适配（SQLite/JSON）
    schemas/        # Pydantic/JSON Schema
    tests/          # 单元/集成测试
    scripts/        # 运维脚本/迁移脚本
    data/           # 本地开发数据
    logs/           # 本地日志（开发环境）
  frontend/
    public/         # 静态资源（favicon 等）
    src/
      components/   # UI 组件
      services/     # API 调用封装
      state/        # 前端状态管理
      utils/        # 工具函数
      styles/       # 样式
      assets/       # 图片/字体
```

## 约定
- 空目录已放置 `.gitkeep` 以便版本管理保留结构。
- 后续如需迁移到 `frontend/src`，建议先稳定 API 再搬迁静态入口文件。
