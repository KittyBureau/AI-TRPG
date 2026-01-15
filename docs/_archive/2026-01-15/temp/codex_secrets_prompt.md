# Codex 提示词：最小可用密钥获取 API（本地加密文件 + 运行时口令）

> 直接将以下内容整体复制给 Codex 使用。  
> 目标：在现有 FastAPI 项目中，以**最小改动**引入安全的 API Key 管理方式，并替换原有环境变量直读逻辑。

---

## 一、背景

当前项目通过：

```python
os.environ["DEEPSEEK_API_KEY"]
```

直接读取 API Key。  
现在需要支持：

- 优先级 1：Windows 环境变量 `DEEPSEEK_API_KEY`
- 优先级 2：本地 **加密文件**（运行时口令解锁）

不引入前端，不做复杂设计，仅实现 **MVP 级别安全方案**。

---

## 二、总体约束（必须遵守）

- 不重构、不重写原有业务逻辑
- 以新增模块为主
- 解密后的密钥 **只存在于进程内存**
- 不打印、不记录任何明文密钥或口令
- 加密文件不进入 git
- 仅考虑单用户 / 本地运行

---

## 三、需要新增的模块

### 1️⃣ `secrets/manager.py`

职责：**统一对外提供密钥获取接口**

必须提供以下 API：

```python
get_secret(name: str) -> str
unlock(password: str) -> None
is_unlocked() -> bool
```

行为规范：

- `get_secret("deepseek_api_key")`：
  1. 优先读取环境变量 `DEEPSEEK_API_KEY`
  2. 若不存在：
     - 未解锁 → 抛出 `SecretsLockedError`
     - 已解锁 → 从进程内存缓存返回
- 模块内部维护一个 **进程级缓存 dict**
- 不允许在模块外直接访问缓存

---

### 2️⃣ `secrets/encrypted_file_backend.py`

职责：**从本地加密文件中解密读取密钥**

实现要求：

- KDF：`scrypt`
- 对称加密：`AES-256-GCM`
- 解密对象：`dict[str, str]`
- salt / nonce 必须随机
- JSON + base64 文件格式即可

必须提供：

```python
decrypt_secrets_file(password: str, path: Path) -> dict
```

约束：

- 不实现加密写入（假设文件已存在）
- 解密失败统一抛异常（不区分口令错误或文件损坏）
- 不打印任何敏感信息

---

### 3️⃣ 加密文件路径约定（Windows）

```text
%USERPROFILE%\.ai-trpg\secrets.enc
```

- 路径集中定义为常量
- 后续可扩展为配置项

---

## 四、替换原有 API Key 读取方式

找到原有代码中直接读取：

```python
os.environ["DEEPSEEK_API_KEY"]
```

替换为：

```python
from secrets.manager import get_secret

api_key = get_secret("deepseek_api_key")
```

⚠️ 不允许修改除“获取 key”之外的任何业务逻辑。

---

## 五、最简单的运行时解锁方式（CLI）

在项目启动流程中：

- 若 `get_secret()` 抛出 `SecretsLockedError`
- 使用 `getpass.getpass()` 从控制台读取口令
- 调用 `unlock(password)`
- 解锁成功后继续运行
- 解锁失败 → 抛异常并退出

不需要：

- 重试机制
- 密码修改
- TTL / 自动锁定
- Web API / 前端 UI

---

## 六、异常与安全边界

- 不输出任何明文密钥或口令
- 不写日志、不 print
- 解密失败直接终止程序
- 不区分“密码错误 / 文件损坏”的具体原因

---

## 七、输出要求（给 Codex）

- 只输出 **新增 / 修改的 Python 文件**
- 清楚标注文件路径
- 不输出 README
- 不输出解释说明
- 不生成测试代码

---

## 目标总结（一句话）

> 为当前项目增加一个“像样但不过度设计”的本地密钥解锁与获取能力，并平滑替换 DeepSeek API Key 的读取方式。
