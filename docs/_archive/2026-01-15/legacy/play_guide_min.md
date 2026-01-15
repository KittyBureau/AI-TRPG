# 最小可玩流程（PLAY_GUIDE_MIN）

面向第一次接触本项目的人，按“现在就能玩”的真实能力说明。

## A. 我现在“已经能玩到什么”
- 通过网页输入一句话，与 GM 风格的模型进行简短叙事对话（前端使用 `/turn`）。
- 通过 `/api/chat/send` 创建/继续会话，并在本地保存聊天记录（带 `conversation_id`）。
- 使用角色生成器创建角色 JSON，并保存到本地角色目录。
- 使用世界移动接口查询可走路径并执行一次移动，更新世界状态文件。
- 使用 sample world 直接跑一局最小地图（无需额外配置世界文件）。
- 通过会话文件与世界状态文件，看到状态变化的可追溯记录。
- 前端入口文件：`frontend/public/index.html`，启动后访问 `http://127.0.0.1:8000/`。
- 有状态聊天测试页：`frontend/public/chat_history.html`，用于 `conversation_id` 续聊与 Debug 观察。

暂时不能做的事（当前阶段不支持）：
- 战斗、技能检定、物品/金钱系统、复杂规则裁定。
- 聊天自动触发世界移动（世界移动需要手动调用接口）。
- 前端页面直接展示/编辑世界状态或会话存档。
- 多角色/多玩家联动与正式任务系统。

## B. 当前阶段的规则定义（最小规则集）
- GM 是“系统 + 代码裁决”，模型只负责生成叙事文本，不具备最终裁判权。
- 世界状态的权威更新只发生在后端代码（例如 `/api/world/apply_move`）。
- `/turn` 使用内置 system prompt（见 `backend/services/llm_client.py`），只喂入“system + 用户输入”。
- `/api/chat/send` 使用 system prompt 文件（`backend/prompts/system/context_full.txt`），并按配置注入信息。
- 注入信息来自 `~/.ai-trpg/config.json` 指定的路径（相对路径以仓库根目录为基准解析）。
- 典型注入块包括：角色卡、规则文本、世界状态、最近对话历史（有配置才会注入）。
- 前端默认调用 `/turn`（不写会话文件）；需要会话存档请使用 `/api/chat/send`。

最小回合规则（当前实现）：
1. 玩家输入一句自然语言。
2. 系统将输入交给模型生成叙事回应。
3. 若需要世界变化（如移动），当前需手动调用世界移动接口执行。
4. 返回结果，进入下一回合。

## C. 角色创建流程
### 1) 前端方式
- 进入角色页面：浏览器打开 `http://127.0.0.1:8000/character`。
- 页面文件：`frontend/public/character.html`。
- 填写“Input”文本（角色概念描述），点击 “Generate”。
- 成功后显示：
  - Comment（模型评价）
  - Status（保存路径，例如 `data/characters/xxx.json`）

### 2) 接口方式（curl 示例）
角色创建接口：`POST /api/characters/generate`
以下 curl 示例以 PowerShell 为例，使用 `curl.exe` 避免别名。

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/characters/generate -H "Content-Type: application/json" -d '{"user_text":"生成一个谨慎的巡逻者，擅长观察，有一个明确目标。"}'
```

响应关键字段：
- `status`: `"OK"` 或 `"NAME_CONFLICT"`
- `character`: 角色 JSON
- `saved_path`: 保存路径（相对仓库根目录）

保存位置：
- 角色文件：`data/characters/<character_id>.json`
- 名称索引：`data/characters/_name_list.json`

重名处理：
- 返回 `status: NAME_CONFLICT`，前端会提示改名。
- 接口可用 `/api/characters/rename_and_save` 保存新名。

## D. 世界 / 地图准备（最小可玩）
静态世界文件与状态文件的区别：
- 静态世界（地图结构）：`backend/storage/worlds/sample_world.json`
- 世界状态（实时变化）：`backend/storage/runs/sample_world_state.json`

如何使用 sample world 启动：
- 默认接口固定使用以上两份 sample 文件（当前 API 不支持切换路径）。
- sample world 的实体：
  - `pc_001` 初始位置：`loc_town_gate`

世界状态何时更新：
- 调用 `/api/world/apply_move` 后写回 `sample_world_state.json`（更新位置、时间、facts）。

## E. 从 0 到“走一步”的完整游玩流程（照做清单）
前提：在仓库根目录执行以下命令。

1) 创建并激活虚拟环境
```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
```

2) 安装依赖
```powershell
python -m pip install -r backend/requirements.txt
```

3) 配置模型 API（会写入本地配置与密钥）
```powershell
python -m backend.secrets.cli
```
提示中建议选择 `Feature=all`，填写 provider、API key、base_url、model 等。
生成文件：
- `~/.ai-trpg/secrets.enc`
- `~/.ai-trpg/config.json`

4) 启动后端
```powershell
python -m uvicorn backend.app.main:app --reload
```

5) 打开前端
- 浏览器访问：`http://127.0.0.1:8000/`
6) 打开带上下文测试页（可选）
- 浏览器访问：`http://127.0.0.1:8000/chat_history.html`

7) 创建角色（前端或 API）
- 前端：`http://127.0.0.1:8000/character`

8) 启动/进入一个会话（API）
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/chat/send -H "Content-Type: application/json" -d '{"user_text":"我站在城门口，观察四周的动静。"}'
```
返回包含 `conversation_id`，并在本地创建会话文件。

9) 成功触发一次世界变化（移动）
- 先查路径：
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/world/get_movement_paths -H "Content-Type: application/json" -d '{"entity_id":"pc_001","max_depth":2,"max_paths":5,"risk_ceiling":"medium"}'
```
- 再移动（示例路径）：
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/world/apply_move -H "Content-Type: application/json" -d '{"entity_id":"pc_001","path_id":"loc_town_gate->loc_market"}'
```

10) 验证文件变化
- 会话文件：`backend/data/conversations/<conversation_id>.json`（新增消息与 meta）
- 世界状态：`backend/storage/runs/sample_world_state.json`（位置与 time 变化）

## F. 玩家输入示例（≥ 3）
- 纯观察：`我在城门附近停下，仔细听周围的脚步声与车轮声。`
- 明确移动：`我沿着通往集市的路向北走，注意观察商贩与守卫。`
- 与 NPC 对话：`我走到酒馆老板面前，礼貌地询问昨晚是否有陌生人进城。`

## 推荐的最小可玩回合约定（非强制）
每次输入尽量包含：
- 意图（看 / 走 / 问 / 搜索）
- 目标（地点 / 人 / 物）
- 风格（谨慎 / 快速 / 隐蔽）

示例：
- `我谨慎地沿着街道向北走，注意观察路口。`
- `我向酒馆老板打听昨晚是否有陌生人进城。`
- `我检查房间，寻找能派上用场的工具。`

## G. 常见问题（Troubleshooting）
- JSON 解析失败：`/turn` 要求模型输出严格 JSON；检查 provider 是否支持 JSON 输出，或更换模型。
- 角色创建失败/重名：返回 `NAME_CONFLICT` 时需改名；前端会提示重命名。
- 世界状态不更新：确认 `entity_id` 与 `path_id` 合法，且使用 sample world 的默认实体 `pc_001`。
- 找不到 key / config：确保已运行 `python -m backend.secrets.cli` 并生成 `~/.ai-trpg/config.json` 与 `~/.ai-trpg/secrets.enc`。
- 会话文件位置：`backend/data/conversations/<conversation_id>.json`（32 位 hex 文件名）。

## 附录：关键接口字段（最小说明）
- `/api/chat/send` 请求：`user_text`（必填），`conversation_id`（可选）。
- `/api/chat/send` 返回：`conversation_id`，`assistant_text`。
- `/api/world/get_movement_paths` 请求：`entity_id`（必填），`max_depth`/`max_paths`/`risk_ceiling`（可选）。
- `/api/world/get_movement_paths` 返回：`from_location_id`，`paths[]`（含 `path_id`、`to_location_id`、`total_time`、`max_risk`）。
- `/api/world/apply_move` 请求：`entity_id`、`path_id`（必填）。
- `/api/world/apply_move` 返回：`status`，`from_location_id`，`to_location_id`，`total_time`，`max_risk`，`time`。
