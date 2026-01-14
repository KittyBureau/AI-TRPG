# Map Generate 人工回归 / 冒烟测试说明（非确定性）

## 测试定位
- 类型：人工回归 / 冒烟测试
- 目的：验证 map_generate 在真实运行条件下的**系统工具链路与状态安全性**
- 允许：LLM 自行判断 dialog_type
- 不做：确定性回归、dialog_type/错误文案精确断言
 - 说明：本测试用于验证系统在真实运行条件下的健壮性与行为边界，而非验证模型输出的确定性

## 核心通过标准
- 成功用例：`applied_actions` 中**实际执行** `map_generate`
- 失败用例：`map_generate` **未执行** 且 **campaign.json 语义未变化**
- 权威性：
  - `reachable_area_ids` 为地图权威
  - `map.connections` 为派生索引（语义一致即可，不校验顺序）
- 连通性：同一 parent 层级内**无孤立**
- 状态：`positions_parent` / `positions_child` 存在，父层位置不被覆盖

## 测试入口
- 唯一入口：`POST /api/chat/turn`
- 前置：FastAPI 运行于 http://127.0.0.1:8000，LLM 配置有效

## 结果判定语义
- PASS
  - 成功用例：系统执行 `map_generate`（`applied_actions` 命中）
  - 失败用例：系统明确拒绝（`tool_feedback.failed_calls` 命中 `map_generate`）
- FAIL
  - 应拒绝的用例被执行（`applied_actions` 命中 `map_generate`）
  - 出现权威状态副作用（campaign.json 语义变化）
- SKIP / INCONCLUSIVE
  - LLM 未发起 `map_generate`
  - 或输出不规范导致无法解析
  - 视为未覆盖该分支，而非系统错误
  - SKIP 在当前架构下是合法且预期的结果

## conflict_report 的角色
- 当 LLM 在叙事中声称执行/尝试工具，但未实际发起 tool_call 时：
  - conflict_report 可能记录 `tool_result_mismatch`
  - 系统可能触发重试
- 在人工回归中：
  - 该行为视为 guard / retry 机制正常工作
  - 不视为失败

## MAP_TEST_STRICT
- `MAP_TEST_STRICT=0`（默认）：inconclusive → SKIP
- `MAP_TEST_STRICT=1`：inconclusive → 失败（用于调试或未来 CI 实验）

## 测试流程
### 流程 A：/docs 手工执行
1. 打开 http://127.0.0.1:8000/docs
2. 调用 `POST /api/campaign/create` 创建新 campaign
3. 在 `POST /api/chat/turn` 中依次执行 Case A~E
4. 每次执行后检查 `storage/campaigns/<campaign_id>/campaign.json`

### 流程 B：脚本批量执行
1. 从 repo root 运行脚本：`python backend/tests/test_map.py`
2. 如需调整 LLM 诱导重试次数，设置环境变量 `MAP_TEST_MAX_ATTEMPTS`（默认 3）
3. 脚本遇到 LLM 未按预期发起 tool_call 时会标记为 INCONCLUSIVE，可重跑

## 用例
### Case A：根层地图生成
- 输入：parent_area_id = null，size=6
- 期望：
  - 执行 map_generate
  - 新增 6 个 area（parent=null，含 reachable）
  - 无孤立；connections 与 reachable 语义一致

### Case B：子地图生成
- 输入：parent_area_id = 任一真实根层 area（动态选择），size=5
- 期望：
  - 执行 map_generate
  - 新增 5 个子层 area（parent 正确）
  - 父区域 reachable **包含至少一个**新子 area（不固定 entry）
  - 子层无孤立；connections 语义一致

### Case C：非法 parent
- 输入：parent_area_id 不存在
- 期望：
  - 不执行 map_generate
  - campaign.json 语义未变化

### Case D：size 越界
- 输入：size=31
- 期望：
  - 不执行 map_generate
  - campaign.json 语义未变化

### Case E：allowlist 禁止
- 前置：临时移除 allowlist 中的 map_generate
- 期望：
  - 不执行 map_generate
  - campaign.json 语义未变化

## 备注
- 不断言 dialog_type
- 不断言失败 reason/status 文案
- 不校验 connections 顺序
- 本文档用于人工回归/冒烟测试，不作为 CI 严格回归
- 测试允许 LLM 自行判断 dialog_type，不作为确定性回归测试使用

## 不覆盖的内容（当前阶段）
- dialog_type 判定准确性
- LLM 是否“听话”地产生 tool_calls
- UI 行为
- 地图移动路径的玩法验证（仅测生成）
