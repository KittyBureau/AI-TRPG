# Codex 提示词：绝对路径清理与相对路径重构（一次性执行）

## 角色设定
You are a senior software engineer specializing in cross-platform, multi-device compatible project structures.
Your task is to refactor file path handling to remove hard-coded absolute paths and make the project portable.

---

## 项目背景

- 原工作路径（已废弃）：
  <legacy_repo_root>

- 当前需求：
  - 项目需要在多台设备（公司 / 家中 / 不同盘符）使用
  - 通过 Git 仓库同步
  - clone 到任意路径后即可直接运行

---

## 核心目标

将 **所有硬编码绝对路径** 改为 **相对路径或基于项目根目录的动态路径**，保证跨设备兼容性。

---

## 任务要求（必须全部完成）

### 1. 全仓库扫描

扫描整个仓库，找出并处理以下问题：

- 硬编码的绝对路径，例如：
  - <legacy_repo_root>
  - 任何包含盘符（例如 `X:`）的路径
- Windows 路径分隔符（反斜杠）
- 假设固定运行目录的逻辑，例如：
  - os.chdir(...)
  - process.cwd() 被当作稳定基准使用

扫描范围包括但不限于：

- Python 文件
- JavaScript / TypeScript
- JSON / YAML / 配置文件
- README 或文档中“用于实际运行”的路径示例

---

### 2. 路径重构规则（强制遵守）

#### Python

- 使用 `pathlib.Path`
- 基于当前文件定位项目根目录，例如：

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[n]
```

- 禁止：
  - 再次写入任何绝对路径
  - 依赖固定的工作目录

#### Node / Web

- 使用：
  - CommonJS：`__dirname`
  - ESM：`import.meta.url`
- 所有路径必须通过这些基准构造

#### 配置文件

- 改为相对路径
- 或由代码在运行时注入 base path
- 配置文件中不得出现盘符

---

### 3. 引入统一路径入口（如有必要）

如项目中路径使用分散，允许新增：

- Python：`paths.py`
- Node：`path_utils.ts` / `path_utils.js`

集中定义：

- project_root
- data_dir
- storage_dir
- config_dir

其他模块必须引用该入口，不得自行拼路径。

---

### 4. 行为约束

- 不新增业务功能
- 不改变原有功能行为
- 文件读写结果必须与原逻辑一致
- 不引入第三方依赖（标准库除外）

---

### 5. 输出要求

你需要：

1. 实际修改代码（不是只给建议）
2. 明确列出：
   - 修改了哪些文件
   - 每类路径问题采用的修复策略
3. 对于 **无法安全自动修改的路径**：
   - 明确指出文件位置
   - 说明原因
   - 给出人工修复建议

---

## 最终验收标准（一句话）

After refactoring, the project must run correctly regardless of where the repository is cloned on any machine.
