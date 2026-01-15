# 世界空间与移动系统规范（供 Codex 实现）

## 目的
本规范用于实现 **空间一致、低幻觉、可扩展** 的世界移动系统。
大模型不负责记忆地图，只通过工具获取“可移动路径链”并做选择。

本规范**不包含具体代码**，仅定义数据结构与工具协议，供 Codex 实现。

---

## 一、核心原则

1. **单一事实源**
   - 实体当前位置只存在于 `entity.location_id`
   - 空间连接只存在于 `world_graph`

2. **模型不记地图**
   - LLM 只能调用工具获取可达路径
   - 不允许自行生成地点或路径

3. **路径 = 链**
   - 返回的是 1~N 跳的路径链，而非单个邻居

---

## 二、数据模型规范（最小集）

### 1. Location（地点节点）

```json
{
  "id": "loc_xxx",
  "name": "地点名称",
  "summary": "一句话描述，用于模型理解",
  "tags": ["city", "market"]
}
```

### 2. Edge（空间连接）

```json
{
  "from": "loc_a",
  "to": "loc_b",
  "type": "road",
  "time": 5,
  "risk": "low",
  "requires": ["has_pass"]
}
```

说明：
- 边为 **单向**
- 双向道路需写两条边
- `requires` 为可选旗标列表

---

### 3. Entity（角色 / NPC）

```json
{
  "id": "pc_001",
  "location_id": "loc_a",
  "flags": ["has_pass"]
}
```

---

### 4. World State（世界状态）

```json
{
  "time": 120,
  "blocked_edges": ["loc_a->loc_b"]
}
```

---

## 三、工具一：获取可移动路径链

### 工具名
`get_movement_paths`

### 输入参数
```json
{
  "entity_id": "pc_001",
  "max_depth": 3,
  "max_paths": 20,
  "risk_ceiling": "medium"
}
```

### 工具行为规范
- 从实体当前位置出发
- 枚举不超过 `max_depth` 的路径链
- 过滤：
  - 被封锁的边
  - 未满足 `requires` 的边
  - 风险超过上限的路径
- 不允许路径内节点重复
- 按 **更短 / 更安全 / 更少跳数** 排序后截断

### 输出格式
```json
{
  "from_location_id": "loc_a",
  "paths": [
    {
      "path_id": "p1",
      "to_location_id": "loc_b",
      "nodes": ["loc_a", "loc_b"],
      "total_time": 5,
      "max_risk": "low"
    }
  ]
}
```

LLM 只能从返回的 `path_id` 中选择。

---

## 四、工具二：执行移动

### 工具名
`apply_move`

### 输入
```json
{
  "entity_id": "pc_001",
  "path_id": "p1"
}
```

### 行为规范
- 校验路径是否合法（或重新计算比对）
- 更新 `entity.location_id`
- 推进世界时间：`time += total_time`
- 追加一条事实记录（facts）

禁止：
- 顺带修改 NPC / 任务 / 地图

---

## 五、封锁与动态变化

- 不直接删除或修改原始边
- 使用 `blocked_edges` 或 `edge_overrides`
- 路径工具需读取该状态层

---

## 六、LLM 使用约束（必须遵守）

- 不得输出不存在的地点 ID
- 不得直接声明“角色到达某地”
- 移动必须通过工具完成
- 若工具返回错误，需重新选择合法路径

---

## 七、最小可测试世界要求

为便于开发测试，至少准备：

1. 10~20 个地点节点
2. 含分叉与环的连接图
3. 1 个实体（含 flags）
4. 初始 world state

---

## 八、实现验收标准（给 Codex）

- 相同输入 → 稳定输出
- 无死循环、无路径爆炸
- 所有路径均可逐边验证
- 非法移动必被拒绝

---

## 设计目标总结

该系统优先保证：
- 空间一致性
- 可校验性
- 可与剧情系统解耦
- 低 token、低幻觉风险

