# AI-TRPG API 测试说明（V1）
日期：2026-01-14

> 目的  
> 本文档用于在**无前端 UI**的情况下，通过 API 验证 AI 跑团系统的完整核心流程（Stage 1–4）。  
> 适用于：开发测试、回归验证、Codex 自测。

---

## 一、测试前准备

### 1.1 启动服务
```bash
uvicorn backend.api.main:app --reload
```

### 1.2 LLM 配置（Stage 4）
1. 复制模板：
   - `storage/config/llm_config.example copy.json` → `storage/config/llm_config.json`
2. 编辑 `storage/config/llm_config.json` 的 `current_profile` 与 profile 字段
3. 首次调用 `/api/chat/turn` 时：
   - 控制台会提示输入 API key（不回显）
   - 然后提示设置/输入本地口令（不回显）
   - key 会加密保存至 `storage/secrets/keyring.json`

> 说明：Stage 4 依赖真实 LLM；若未配置 llm_config.json 或未输入 key，将无法执行 Stage 4 的步骤。

### 1.3 运行自动化测试
推荐从仓库根目录执行（不要依赖 PYTHONPATH 环境变量）：
```bash
python -m pytest -q
```

---

## 二、核心测试流程（推荐顺序）

### Step 1：创建战役
**POST /api/campaign/create**

请求体（最小）：
```json
{}
```

返回示例：
```json
{ "campaign_id": "camp_0001" }
```

验证点：
- storage/campaigns/<campaign_id>/campaign.json 生成
- settings_snapshot 与 settings_revision=0 存在

---

### Step 2：查看战役列表
**GET /api/campaign/list**

验证点：
- 新建战役可被列出
- active_actor_id 正确

---

### Step 3：切换当前行动角色（可选）
**POST /api/campaign/select_actor**

```json
{
  "campaign_id": "camp_0001",
  "active_actor_id": "pc_002"
}
```

验证点：
- campaign.json 中 active_actor_id 更新

---

### Step 4：普通对话（无工具）
**POST /api/chat/turn**

```json
{
  "campaign_id": "camp_0001",
  "user_input": "I look around the room."
}
```

验证点：
- 返回 narrative_text
- turn_log.jsonl 新增 1 行
- 无 tool_calls / applied_actions
- state_summary 与 campaign.json 中 actors 状态一致（positions/hp/character_states 为派生值）

---

### Step 5：工具调用（移动）
> 破坏性变更：move 只允许 args={actor_id,to_area_id}，包含 from_area_id 会返回 invalid_args。

```json
{
  "campaign_id": "camp_0001",
  "user_input": "tool: {\"id\":\"call_001\",\"tool\":\"move\",\"args\":{\"actor_id\":\"pc_001\",\"to_area_id\":\"area_002\"},\"reason\":\"move\"}"
}
```

验证点：
- applied_actions 含 move
- campaign.json 中 actors.pc_001.position 更新
- turn_log.jsonl 记录 applied_actions 与 state_summary

---

### Step 6：工具调用（血量变化）
```json
{
  "campaign_id": "camp_0001",
  "user_input": "tool: {\"id\":\"call_002\",\"tool\":\"hp_delta\",\"args\":{\"target_character_id\":\"pc_001\",\"delta\":-10,\"cause\":\"trap\"},\"reason\":\"damage\"}"
}
```

验证点：
- hp 变化
- actors.pc_001.character_state 进入 dying（当前实现无 dead 自动切换）
- rules.hp_zero_ends_game 生效

---

### Step 7：冲突拦截测试（Stage 4）
输入诱导 AI 叙事错误：
```json
{
  "campaign_id": "camp_0001",
  "user_input": "I move to the next room without using any tools."
}
```

验证点：
- 第一次生成被拦截
- retry 发生
- 若最终成功：1 条日志 + conflict_report
- 若失败：无日志 + conflict_report 返回

---

## 三、失败与异常验证

### 3.1 非法工具
- 缺少参数
- tool 不在 allowlist

验证点：
- tool_feedback.failed_calls 有内容
- campaign.json 不变

### 3.2 超过重试次数
验证点：
- response 中 conflict_report.retries = max
- turn_log.jsonl 无新增行

---

## 四、文件级验证清单

### 必须存在
- storage/campaigns/<campaign_id>/campaign.json
- storage/campaigns/<campaign_id>/turn_log.jsonl

### turn_log.jsonl 每行必须包含
- turn_id / timestamp
- dialog_type / dialog_type_source
- assistant_text
- assistant_structured.tool_calls
- applied_actions
- state_summary（positions / hp / character_states）

---

## 五、回归测试建议
- 每次修改 tool / state_machine / conflict_detector 后
- 重新跑 Step 4–7
- 对比 turn_log.jsonl 差异

### map_generate 人工回归 / 冒烟（非确定性）
- 入口脚本：`backend/tests/test_map.py`
- 定位：人工回归 / 冒烟测试，允许 LLM 不发起 tool_calls
- 结果判定：
  - PASS：系统执行 map_generate 或明确拒绝（failed_calls）
  - FAIL：应拒绝用例被执行，或出现权威状态副作用
  - SKIP：LLM 未发起或输出不可解析（合法且预期）
- 说明：该测试用于验证系统边界与健壮性，不作为 CI 严格回归

---

## 六、结论
当以上步骤全部通过：
- 系统核心逻辑稳定
- AI 行为受控
- 状态可审计、可回放

此时可安全进入前端或玩法层开发。
