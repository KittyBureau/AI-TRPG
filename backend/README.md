# 最小大语言模型原型

## 依赖
- Python 3.13+
- 本地加密密钥文件 + 配置 JSON 位于 `~/.ai-trpg/`

## 安装
```
python -m pip install -r backend/requirements.txt
```

## 运行
```
python -m uvicorn backend.app.main:app --reload
```

浏览器打开 `http://127.0.0.1:8000`。

## 文档
- `docs/ai/AI_INDEX.md`
- `docs/ai/CONVENTIONS.md`

## 服务模块
- `backend/services/llm_client.py`（大语言模型调用 + JSON 校验）
- `backend/services/character_service.py`（角色生成 + 保存）
- `backend/services/world_movement.py`（移动路径 + 移动结算）

## 配置
- 在 `~/.ai-trpg/config.json` 中配置路由与提供方参数。
- 通过 `python -m backend.secrets.cli` 将 API 密钥写入 `~/.ai-trpg/secrets.enc`。
- `config.json` 支持 `routing.all`，用于所有功能的默认提供方。
