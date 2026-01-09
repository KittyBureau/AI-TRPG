# 世界空间与移动系统实现说明

本文档描述当前代码实现与规范的对应关系，以及数据文件布局。

## 目录与文件

- 静态世界：`backend/storage/worlds/sample_world.json`
  - `locations`：地点节点列表
  - `edges`：单向边列表（`from/to/type/time/risk/requires`）
- 动态状态与事实：`backend/storage/runs/sample_world_state.json`
  - `time`：世界时间
  - `blocked_edges`：封锁边列表（格式 `loc_a->loc_b`）
  - `entities`：实体列表（`id/location_id/flags`）
  - `facts`：事实记录（移动完成时追加）

静态世界与动态状态分离，避免混存。

## 服务模块

实现位于 `backend/services/world_movement.py`：

- `get_movement_paths(...)`
  - 从 `entity.location_id` 出发枚举 1..N 跳路径
  - 过滤封锁边、`requires` 未满足、风险超过上限
  - 禁止路径内节点重复
  - `max_risk` 取路径中**最大**风险
  - 结果排序：`total_time` 更短 → `max_risk` 更低 → 跳数更少 → `path_id`
  - `path_id` 为稳定签名：`loc_a->loc_b->loc_c`

- `apply_move(...)`
  - 解析 `path_id` 并逐边校验
  - 更新 `entity.location_id` 与 `time`
  - 追加一条 `facts` 记录（`type: move`）

为了稳定输出，边在加载时会排序，路径枚举过程可重复。

## API（薄层）

- `POST /api/world/get_movement_paths`
  - Request
    ```json
    {"entity_id":"pc_001","max_depth":3,"max_paths":20,"risk_ceiling":"medium"}
    ```
  - Response
    ```json
    {"from_location_id":"loc_town_gate","paths":[{"path_id":"loc_town_gate->loc_market","to_location_id":"loc_market","nodes":["loc_town_gate","loc_market"],"total_time":2,"max_risk":"low"}]}
    ```

- `POST /api/world/apply_move`
  - Request
    ```json
    {"entity_id":"pc_001","path_id":"loc_town_gate->loc_market"}
    ```
  - Response
    ```json
    {"status":"OK","entity_id":"pc_001","from_location_id":"loc_town_gate","to_location_id":"loc_market","path_id":"loc_town_gate->loc_market","total_time":2,"max_risk":"low","time":2}
    ```

错误时返回 `status: ERROR` 与 `message`。

## References
- `docs/ai/CONVENTIONS.md`
- `docs/ai/ARCHITECTURE.md`
