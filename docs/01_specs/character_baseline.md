# 角色能力现状基线（需求对齐）

日期：2026-02-10  
范围：当前仓库实现（backend/frontend/docs），不含 `_archive` 历史方案。

## 1. 目的

用于在开始“角色生成器”前，统一当前项目中与角色（actor/character）相关的：

- 已实现接口
- 已实现数据结构与行为
- 前端已接入能力
- 明确缺口与下一步约束

本文件描述“现在是什么”，不描述未来实现细节。

## 2. 已实现接口（角色相关）

### 2.1 创建战役并注入角色集合

- `POST /api/v1/campaign/create`
- 请求可包含：
  - `party_character_ids: string[]`
  - `active_actor_id: string`
- 默认行为：
  - 未传 `party_character_ids` 时默认 `["pc_001"]`
  - 未传 `active_actor_id` 时默认取 party 第一个
  - 若 `active_actor_id` 不在 party 中，后端会自动补入

作用：当前“创建角色并入队”的唯一入口是传入角色 ID 列表（仅 ID，不含完整角色档案）。

### 2.2 切换当前行动角色

- `POST /api/v1/campaign/select_actor`
- 入参：
  - `campaign_id`
  - `active_actor_id`
- 约束：
  - 仅允许切换到 `party_character_ids` 内的角色

### 2.3 回合接口按角色执行

- `POST /api/v1/chat/turn`
- 入参：
  - `campaign_id`
  - `user_input`
  - `actor_id`（可选）
- 行为：
  - 未传 `actor_id` 时使用 `selected.active_actor_id`
  - 传入的 `actor_id` 也必须属于 `party_character_ids`

### 2.4 地图视图按角色查看

- `GET /api/v1/map/view?campaign_id=...&actor_id=...`
- `actor_id` 可选；不传时使用 `selected.active_actor_id`
- 返回包含：
  - `active_actor_id`
  - `current_area`
  - `current_area_actor_ids`
  - `reachable_areas`

## 3. 已实现角色数据模型

## 3.1 角色主模型

`ActorState` 当前字段：

- `position: string | null`
- `hp: int`（默认 10）
- `character_state: string`（默认 `"alive"`）
- `meta: object`（默认 `{}`，用于扩展）

## 3.2 战役中的角色容器

`Campaign` 中与角色相关的核心字段：

- `selected.party_character_ids`
- `selected.active_actor_id`
- `actors: Dict[str, ActorState]`

说明：

- `actors[*].position` 是位置权威字段。
- `positions/hp/character_states` 是兼容遗留字段，运行时由 `actors` 派生。

## 4. 已实现角色行为与规则

### 4.1 角色初始化

创建战役时会为 party 角色创建默认 `ActorState`，并落位到初始区域。

### 4.2 角色可被工具修改

已支持工具行为：

- `move`：修改角色位置（必须是当前 active actor）
- `hp_delta`：修改角色 HP，并按规则切换 `character_state`
- `move_options`：只读，不改状态

### 4.3 状态机约束

角色状态允许值：

- `alive`
- `dying`
- `unconscious`
- `restrained_permanent`
- `dead`

其中 `dying` 仅允许对“自己”执行 `hp_delta` 且 `delta > 0`；其他非 `alive` 状态基本禁用工具。

## 5. 前端已接入的角色相关能力

当前前端为原始请求控制台（非业务化角色界面），已接入：

- 创建战役（可填写 party 与 active actor）
- 切换 active actor
- 发起带 `actor_id` 的 turn
- 查看 `state_summary`（包含角色派生状态）
- 地图页按角色查看位置上下文

注：当前不存在“角色生成器”页面或“角色卡管理”页面。

## 6. 明确缺口（与角色生成器直接相关）

以下能力当前未实现：

- 独立角色生成接口（如 `/api/characters/generate`）
- 独立角色查询/保存/重命名接口
- 角色库（跨战役）与战役内角色引用关系
- 角色生成质量约束（schema 校验、重名策略、冲突处理）
- 面向角色管理的前端页面

现有待办已明确记录：`世界生成器，角色生成器制作`。

## 7. 对齐边界（建议作为需求输入）

在不破坏现有架构前提下，角色生成器应优先遵守：

- 路由层仅做 HTTP 映射，业务落在 `backend/app/`
- 角色持久化统一走 `backend/infra/file_repo.py` 与 `storage/`
- `Campaign.selected.party_character_ids` 与 `Campaign.actors` 必须保持一致性
- 回合与工具执行继续以 `active_actor_id` / `actor_id` 为权限与行为入口
- 文档改动需同步 `docs/01_specs/` 与测试指南

## 8. 一句话结论

当前项目已有“战役内角色状态管理”与“按角色执行回合”的骨架，但“角色生成器”仍是未落地模块，可在既有 `Campaign + ActorState` 结构上增量扩展。

## 9. Update (2026-02-10, internal-only)

- Added non-API internal CharacterFact generation persistence flow:
  - `backend/app/character_fact_generation.py`
  - `backend/scripts/generate_character_facts.py`
  - `storage/campaigns/{campaign_id}/characters/generated/*`
- Added runtime CharacterFact read path via facade factory:
  - `backend/app/character_facade_factory.py`
  - `backend/infra/character_fact_store.py`
- This update does not add `/api/characters/*` routes yet.
