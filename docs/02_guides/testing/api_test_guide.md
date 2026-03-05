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
3. 首次调用 `/api/v1/chat/turn` 时：
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
**POST /api/v1/campaign/create**

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
**GET /api/v1/campaign/list**

验证点：
- 新建战役可被列出
- active_actor_id 正确

---

### Step 3：切换当前行动角色（可选）
**POST /api/v1/campaign/select_actor**

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
**POST /api/v1/chat/turn**

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

---

## CharacterFact API regression (`/api/v1/campaigns/.../characters`)

Minimal checks after backend changes:

1. `POST /api/v1/campaigns/{campaign_id}/characters/generate`
   - returns refs only (`request_id`, `batch_path`, `individual_paths`, counts, warnings)
   - does not return full `items`
   - writes:
     - `storage/campaigns/{campaign_id}/characters/generated/batch_{utc_ts}_{request_id}.json`
     - `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.draft.json`
   - persisted `character_id` must not be `__AUTO_ID__`

2. conflict handling
   - submit same `request_id` under same `campaign_id` twice
   - second call returns `409 Conflict`
   - no new batch file is created

3. parameter validation
   - `tone_vocab_only=true` with empty `allowed_tones` -> `400`
   - `count<=0` or empty `constraints.allowed_roles` -> `400`

4. schema validation guard
   - if normalize output is schema-invalid -> `422`

5. query APIs
   - `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches`
   - `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}`
   - `GET /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`

6. docs/openapi routing regression
   - `/api/v1/openapi.json` is reachable
   - `/api/v1/docs` is reachable

## CharacterFact behavior matrix (test-authoritative)

Use this section as the source of truth for current API behavior. Do not infer beyond these rows.

### GET `/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`

| Status | Case | Expected behavior | Test evidence |
| --- | --- | --- | --- |
| Guaranteed | draft exists and is valid | return `200` with draft payload | `backend/tests/test_character_fact_api.py:250` |
| Guaranteed | draft missing, batch has the character | return `200` via batch fallback | `backend/tests/test_character_fact_api.py:250` |
| Guaranteed | draft JSON unreadable, batch has the character | return `200` via batch fallback | `backend/tests/test_character_fact_api.py:282` |
| Guaranteed | draft readable but schema-invalid (`meta.unknown`) | return `422` | `backend/tests/test_character_fact_api.py:308` |
| Unspecified | draft missing and batch missing | status/shape not frozen | not asserted |
| Unspecified | campaign missing on GET fact | status/shape not frozen | not asserted |

### POST `/api/v1/campaigns/{campaign_id}/characters/generate` error precedence

| Status | Case | Expected behavior | Test evidence |
| --- | --- | --- | --- |
| Guaranteed | valid request | return `200` refs-only response (`batch_path`, `individual_paths`, `count_requested`, `count_generated`, `warnings`) | `backend/tests/test_character_fact_api.py:85` |
| Guaranteed | same `campaign_id` + same `request_id` twice | second call returns `409`; no new batch file | `backend/tests/test_character_fact_api.py:128` |
| Guaranteed | `tone_vocab_only=true` and empty `allowed_tones` (campaign exists) | return `400` | `backend/tests/test_character_fact_api.py:156` |
| Guaranteed | normalize output schema-invalid | return `422` | `backend/tests/test_character_fact_api.py:189` |
| Guaranteed | campaign missing + payload also violates `allowed_tones` rule | return `404` (precedence over this `400`) | `backend/tests/test_character_fact_api.py:173` |
| Unspecified | other multi-error combinations | precedence not frozen | not asserted |

---

## Frontend click-test checklist (V1.1 quick path)

## Character Library + Party Load regression (`/api/v1/characters/library`, `/api/v1/campaigns/.../party/load`)

Minimal checks after backend changes:

1. `POST /api/v1/characters/library`
   - request body: `{id?, name, summary?, tags?, meta?}`
   - response contains: `ok`, `character_id`, `fact`
   - writes `storage/characters_library/{character_id}.json`

2. `GET /api/v1/characters/library`
   - returns summary list: `[{id,name,summary,tags}]`
   - source is only `storage/characters_library/*.json`
   - broken JSON files are skipped (list still `200`)

3. `GET /api/v1/characters/library/{character_id}`
   - returns normalized full payload
   - missing id returns `404`

4. `POST /api/v1/campaigns/{campaign_id}/party/load`
   - request body: `{character_id, set_active_if_empty?}`
   - ensures `actors[character_id]` exists
   - writes `actors[character_id].meta.profile`
   - appends `selected.party_character_ids` when absent
   - sets `selected.active_actor_id` only when active is empty and `set_active_if_empty=true`

5. routing regression
   - `/api/v1/openapi.json` includes `/characters/library` and `/campaigns/{campaign_id}/party/load`

Frontend check entry (legacy note):

- `frontend/index.html` is deprecated and redirects to `play.html`.
- Use `frontend/play.html` for campaign/party/actor flow checks.
- Use `frontend/debug.html` for raw request/response inspection.
- For endpoint-level lifecycle and settings checks, prefer direct API calls in this guide.

---

## Turn adopted profile trace gate (new)

1. Keep default setting (`dialog.turn_profile_trace_enabled=false`)
   - Call `POST /api/v1/chat/turn`
   - Verify response has no top-level `debug` field.

2. Enable trace setting
   - Call `POST /api/v1/settings/apply`:
     ```json
     {
       "campaign_id": "camp_0001",
       "patch": {
         "dialog.turn_profile_trace_enabled": true
       }
     }
     ```
   - Call `POST /api/v1/chat/turn` again.
   - Verify response contains top-level:
     - `debug.used_profile_hash` (stable hash string).
     - `debug.used_profile_version` only when profile payload provides it.
     - `debug.used_prompt_name`
     - `debug.used_prompt_version`
     - `debug.used_prompt_hash`
     - `debug.used_prompt_source_hash`
     - `debug.used_prompt_rendered_hash`
     - `debug.prompt` object (`name`, `version`, `source_hash`, `rendered_hash`, `variables`, `fallback`)
     - `debug.used_flow_name`
     - `debug.used_flow_version`
     - `debug.used_flow_hash`
     - `debug.flow` object (`name`, `version`, `hash`, `fallback`)

3. Prompt context assembly verification (mock/spy LLM in tests)
   - Assert turn context includes `adopted_profiles_by_actor`.
   - Assert `Context.actors[*].meta` does not duplicate full `profile`.
   - Do not assert natural-language output text.

---

## Frontend one-click Run Loop check

Legacy Run Loop UI in `frontend/index.html` is soft-deprecated.

Use one of:

1. API-first chain checks in this document.
2. Play flow checks in `docs/02_guides/testing/active_actor_integration_smoke.md`.

---

## MVP Playable v0 contract additions (2026-03-04)

When validating current mainline behavior, include these checks:

1. New tool in allowlist
   - `campaign.json.allowlist` includes `inventory_add`.

2. `inventory_add` turn behavior
   - submit `/api/v1/chat/turn` with one `inventory_add` tool_call.
   - expect one `applied_actions[*].tool == "inventory_add"`.
   - expect item quantity change persisted at `campaign.json.actors.<active_actor_id>.inventory`.

3. `state_summary` extensions in turn response
   - `state_summary.objective`
   - `state_summary.active_area_id`
   - `state_summary.active_area_name`
   - `state_summary.active_area_description`
   - `state_summary.active_actor_inventory`

4. World payload extensions
   - `GET /api/v1/campaigns/{campaign_id}/world` includes:
     - `world_description`
     - `objective`
     - `start_area`

5. Turn actor_context / effective actor checks
   - request with execution context:
     ```json
     {
       "campaign_id": "camp_0001",
       "user_input": "....",
       "execution": { "actor_id": "pc_002" }
     }
     ```
   - response must include top-level `effective_actor_id == "pc_002"`.
   - compatibility request without `execution.actor_id` must still work (fallback to selected active actor).

6. Actor context mismatch rejection
   - send a turn with `execution.actor_id="pc_002"` and a tool call carrying `args.actor_id="pc_001"`.
   - expect failed call reason `actor_context_mismatch` and no state mutation for the wrong actor.

7. Same-campaign turn lock
   - trigger two concurrent `/api/v1/chat/turn` requests for the same `campaign_id`.
   - expect one request can fail with `409 Conflict` and detail containing "already running".

## Scene Interaction v1 additions (2026-03-04)

1. `campaign.json` entity authority
   - confirm `campaign.json` contains top-level `entities` dictionary.
   - confirm IDs are stable keys and each entity carries `loc`, `verbs`, `state`, `props`.

2. map view contract
   - call `GET /api/v1/map/view?campaign_id=...&actor_id=...`.
   - verify response includes `entities_in_area[]`.
   - verify each item includes: `id`, `kind`, `label`, `tags`, `verbs`.

3. `scene_action` strict turn call
   - call `/api/v1/chat/turn` with a strict `UI_FLOW_STEP` prompt that executes exactly one `scene_action`.
   - include `execution.actor_id` in request payload.
   - verify response:
     - `effective_actor_id` equals `execution.actor_id`.
     - `applied_actions[*].tool == "scene_action"`.
     - `applied_actions[*].result.ok` exists.

4. `scene_action` failure semantics
   - verify logical failures return `result.ok=false` and `result.error.code`:
     - `not_reachable`
     - `not_allowed`
     - `locked`
     - `carry_limit`
   - verify actor mismatch still uses `tool_feedback.failed_calls[*].reason=actor_context_mismatch`.

5. persistence check for entity changes
   - after `take` / `drop` / `detach`, verify `storage/campaigns/<campaign_id>/campaign.json`
     reflects updated `entities.<entity_id>.loc` / `kind` / `state` values.

## Campaign get endpoint regression (`/api/v1/campaign/get`)

1. call:
   - `GET /api/v1/campaign/get?campaign_id=<campaign_id>`
2. verify response fields:
   - `campaign_id`
   - `selected.party_character_ids` (list)
   - `selected.active_actor_id` (string)
   - `actors` (actor id list)
3. verify `404` when campaign does not exist.
