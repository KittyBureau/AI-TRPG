# Codex 提示词（临时文档）：多 Key 管理 + OpenAI 兼容 API + 本地配置文件

> 将本文件内容整体复制给 Codex 执行。  
> 目标：在现有 FastAPI 项目中，把“单一 API Key”升级为“多 Provider / 多 Key + 按功能路由”，并将 **URL / model / temperature 等配置**全部放到**本地 JSON 配置文件**中。  
> 注意：命名、文件落点与代码结构请 **Codex 根据项目实际自行决定**（保持一致性与最小改动优先）。

---

## 1) 需求总览（MVP）

### 功能路由（固定三类功能）
系统需要支持三类功能的“路由到某个 provider”：
- `chat`（对话）
- `world_gen`（世界生成）
- `character_gen`（角色生成）

> 当前所有 provider 的调用方式统一为 **OpenAI API 兼容格式**（OpenAI-compatible REST）。  
> provider 只是一个逻辑名，用于选择 `api_key + base_url + model + temperature` 等配置。

### 关键变化
1) **删除所有环境变量读取 API Key 的逻辑**（不再使用 `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` 等）。  
2) API Key 只从 **本地加密文件**读取（运行时口令解锁），解密后仅存在于进程内存。  
3) 所有 **URL、model、temperature、timeout 等非密钥配置**放在**本地 JSON 文件**中读取。  
4) 目前 **不做配置输入 UI**：配置 JSON 由使用者手动编辑；后续再扩展网页配置输入/保存逻辑。  
5) 需要提供一个最小的“写入/更新密钥”的方式（CLI 交互即可）：使用者录入 API key 时，需要**选择功能**并指定 provider 名称；同时提示使用者去配置文件中填写该 provider 的 `base_url` 等（或允许 CLI 仅录入 key，不录入 url）。

---

## 2) 本地文件约定

### 2.1 加密密钥文件（只存密钥）
- 位置建议：用户目录下的应用文件夹（例如 Windows `%USERPROFILE%\\.ai-trpg\\secrets.enc`）
- 内容：只存 `providers -> api_key`
- 格式：JSON + base64（整体加密）
- 版本号：建议 `version: 1`（如果已有旧结构，请做迁移）

解密后的结构建议：
```json
{
  "version": 1,
  "providers": {
    "providerA": {"api_key": "sk-..."},
    "providerB": {"api_key": "sk-..."}
  }
}
```

> 不在加密文件中保存 base_url/model/temperature 等配置。

### 2.2 明文配置文件（只存配置，不含密钥）
- 位置建议：与 secrets 同目录或项目的可配置路径（例如 Windows `%USERPROFILE%\\.ai-trpg\\config.json`）
- 内容：
  - 三类功能到 provider 的路由：`routing`
  - 每个 provider 的 OpenAI-compatible 配置：`providers`
    - `base_url`（使用者必须填写）
    - `model`（可选默认值）
    - `temperature`（可选）
    - `timeout`（可选）
    - 其他你项目中已支持/常用的参数

建议结构：
```json
{
  "version": 1,
  "routing": {
    "chat": "providerA",
    "world_gen": "providerB",
    "character_gen": "providerA"
  },
  "providers": {
    "providerA": {
      "base_url": "https://.../v1",
      "model": "gpt-4o-mini",
      "temperature": 0.7,
      "timeout_seconds": 60
    },
    "providerB": {
      "base_url": "https://.../v1",
      "model": "some-model",
      "temperature": 0.2,
      "timeout_seconds": 60
    }
  }
}
```

约束：
- 配置文件中 **禁止**出现任何 API key 字段
- 配置缺失时要报错且提示使用者编辑 JSON

---

## 3) 加密方案要求（必须使用标准方案）

- KDF：`scrypt`
- AEAD：`AES-256-GCM`
- salt / nonce 必须随机
- 文件格式可用 JSON + base64
- 解密失败（口令错误/文件损坏）统一抛异常；不要泄露细节
- 禁止在日志/异常中输出明文 key 或口令

需要提供：
```python
decrypt_secrets_file(password: str, path: Path) -> dict
encrypt_secrets_file(bundle: dict, password: str, path: Path) -> None
```

---

## 4) 运行时 API（对项目其他模块的统一入口）

### 4.1 运行时解锁
提供：
- `unlock(password: str) -> None`：解密 secrets.enc，缓存到进程内存
- `is_unlocked() -> bool`
- 未解锁时调用 key 获取应抛出明确异常（例如 `SecretsLockedError`）

### 4.2 按功能获取调用参数（核心）
提供一个统一函数/类（命名由 Codex 决定），给业务层调用：
- 输入：`feature`（chat/world_gen/character_gen）
- 输出：该 feature 对应 provider 的 OpenAI-compatible 调用参数：
  - `api_key`（来自加密文件）
  - `base_url/model/temperature/timeout...`（来自 config.json）

示例接口（仅示意，按项目实际调整）：
```python
get_client_params_for_feature(feature: str) -> {
  "provider": str,
  "api_key": str,
  "base_url": str,
  "model": str,
  "temperature": float,
  "timeout_seconds": int
}
```

行为规则：
1) 从 config.json 的 `routing[feature]` 得到 provider 名称
2) 从 secrets bundle 的 `providers[provider].api_key` 得到 key
3) 从 config.json 的 `providers[provider]` 得到 base_url/model/temperature 等
4) 任一缺失：抛异常并提示修复 config/secrets（但不要泄露 key）

---

## 5) 密钥录入/更新（最小 CLI 交互）

当前不做 Web UI，但仍需要能初始化/更新 secrets.enc。实现一个 CLI 交互入口（可以是一个脚本、或 main 启动参数、或单独模块函数），要求：
- 让使用者选择功能（chat/world_gen/character_gen）
- 让使用者输入 provider 名称（自由文本，未来可扩展为任意模型/服务）
- 让使用者输入该 provider 的 API key（不要回显/不要日志）
- 更新加密文件：写入 `providers[provider].api_key`
- 同时更新明文 config.json 的 `routing[feature] = provider`（可选但推荐；如果不自动改 config.json，则至少输出清晰提示让使用者手动改）

注意：
- 使用者还必须为该 provider 在 config.json 中设置 `base_url`（本需求要求“需要让使用者输入 url”，但当前不做 UI；因此可采用：
  - 方案 A：CLI 也询问 base_url 并写入 config.json（这不算 UI，只是 CLI 输入）
  - 方案 B：CLI 不问 url，但在结束时打印“请编辑 config.json 填写 base_url”提示
  Codex 请选择其一；若选择方案 A，也要确保 config.json 中不写入 key。
- secrets.enc 不存在则创建
- 旧版 secrets（若存在）需迁移到新结构（providers 字典）；若旧版仅有单 key，则导入为 `providers["default"].api_key` 或根据项目已有 provider 名推断（Codex 自行决定，保证可用）

---

## 6) 替换项目中三处功能入口（最小改动）

你需要定位并替换三类功能实际发起 OpenAI-compatible 请求的地方：
- 对话（chat）
- 世界生成（world_gen）
- 角色生成（character_gen）

替换方式：
- 原先固定读取某 env 或固定 key/base_url/model 的逻辑，改为：
  - 调用“按功能获取参数”函数（第 4.2）
  - 用返回的 `api_key/base_url/model/temperature` 构造请求
- 除此之外不重构业务逻辑，不改变接口返回结构

---

## 7) 输出要求（严格）
- 只输出新增/修改的 Python 文件与新增的默认 config.json 模板（如需要）
- 每个文件必须标注路径
- 不输出 README、长解释、不输出测试
- 不引入前端/网页 UI
- 保证项目能运行：未解锁/未配置时给出明确错误提示

---

## 8) 验收清单（Codex 自检）
1) 无环境变量依赖：项目运行不再读取任何 API key env
2) secrets.enc 解锁后：三类功能都能获取到对应 provider 的 key
3) config.json 可控制：routing 与 provider 配置生效（base_url/model/temperature）
4) CLI 录入 key 可创建/更新 secrets.enc，并能把功能路由指向正确 provider（自动或提示用户手动改）
5) 配置缺失时：错误信息清晰但不泄露 key/口令

开始修改。
