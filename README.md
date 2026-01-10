# DocumentsAndDirectives（项目说明）

## 快速开始
```
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements.txt
python -m backend.secrets.cli
python -m uvicorn backend.app.main:app --reload
```
打开：`http://127.0.0.1:8000/`

## 快速入口
- 后端入口：`backend/app/main.py`（兼容入口：`backend/main.py`）
- 前端入口：`frontend/public/index.html`
- 角色工具页：`/character`
- 角色数据目录（运行期，git 忽略）：`data/characters/`
- 世界数据（版本化）：`backend/storage/worlds/`
- 世界状态/事实（样例）：`backend/storage/runs/`

## 密钥与配置
- 加密密钥文件：`~/.ai-trpg/secrets.enc`
- 明文配置文件：`~/.ai-trpg/config.json`
- 使用 `python -m backend.secrets.cli` 注册密钥与路由

## 路由默认值
- `config.json` 支持 `routing.all`，为所有功能指定统一提供方。
- 当某功能未配置路由时，回退到 `routing.all`。

## 人工智能文档索引
- 必读：实现上下文相关功能前先阅读 `docs/TODO_CONTEXT.md`。
- `docs/ai/AI_INDEX.md`（入口）
- `docs/ai/CONVENTIONS.md`（数据放置 + 命名）
- `docs/ai/ARCHITECTURE.md`（当前分层）
- `docs/ai-trpg/README.md`（领域文档）
- `docs/design/dialog_routing.md`（对话路由 + 上下文配置）
- `docs/testing/dialog_routing_test_method.md`（路由测试方法）

## 关键模块
- `backend/services/llm_client.py`：`/turn` 使用 DeepSeek，严格 JSON 校验 + 重试
- `backend/services/character_service.py`：角色生成、改名与保存（DeepSeek JSON + 评语）
- `backend/services/world_movement.py`：移动路径计算 + 移动结算
- `frontend/public/app.js`：首页对话逻辑
- `frontend/public/character.js`：角色工具界面逻辑

## 当前结构
```text
.
  .venv/                # 本地虚拟环境
  backend/
    app/                # 应用入口
      main.py
    services/           # 业务服务
      llm_client.py
      character_service.py
      world_movement.py
    api/                # 保留
    agents/             # 保留
    core/               # 保留
    tools/              # 保留
    storage/            # JSON 夹具 + 样例状态
      worlds/
      runs/
    prompts/            # 提示词模板
    schemas/            # 保留
    tests/              # 保留
    scripts/            # 保留
    data/               # 保留
    logs/               # 保留
    requirements.txt
    README.md
    main.py             # 兼容入口
  frontend/
    public/
      index.html
      app.js
      style.css
      character.html
      character.js
      character.css
    src/                # 保留
  data/
    characters/         # 角色 JSON 文件（运行期，git 忽略）
      *.json
```

## 约定
- 角色文件名 = 经过文件名安全清洗后的 `character.name + .json`
- JSON 以 UTF-8 + indent=2 保存
- 大语言模型功能要求 `~/.ai-trpg/` 下存在密钥 + 配置
- 版本化数据放在 `backend/storage/`；`data/` 为本地运行期目录（git 忽略）

## 在其他设备上使用
1) 安装 Git 与 Python 3.13.1
2) `git clone https://github.com/KittyBureau/AI-TRPG.git`
3) `cd AI-TRPG`
4) 创建并激活 venv：
   - `python -m venv .venv`
   - `./.venv/Scripts/Activate.ps1`
5) 安装依赖：`python -m pip install -r backend/requirements.txt`
6) 配置密钥：`python -m backend.secrets.cli`
7) 运行：`python -m uvicorn backend.app.main:app --reload`

注意：`data/` 与 `backend/data/` 会被 git 忽略。版本化样例在 `backend/storage/`。
