你在一个已能跑通单次对话(/turn)的项目里新增“带上下文（conversation_id续聊）”测试页。要求最小改动、独立页面、用于后续测试与排障。



背景与接口约定（来自项目文档）



现有前端入口：frontend/public/index.html，访问 http://127.0.0.1:8000/



新页面：新增一个独立静态页面，例如 frontend/public/chat_history.html



使用接口：POST http://127.0.0.1:8000/api/chat/send



请求字段：user_text（必填），conversation_id（可选）



响应字段：conversation_id，assistant_text



“带历史/上下文”含义：前端每次续聊都携带 conversation_id，上下文由后端会话文件维护注入；前端不需要把历史 messages 全量发回。



交付物



新增：frontend/public/chat_history.html（可选拆分 chat_history.js / chat_history.css，但优先单文件也行）



修改：frontend/public/index.html 只加一个入口链接到 /chat_history.html，不动现有单次对话逻辑



页面功能（必须实现）

1) 会话与上下文



页面维护一个“当前会话 conversation_id”



首次发送时不传 conversation_id（或传空），由后端创建并返回新的 conversation_id



之后每次发送都携带 conversation_id 续聊，实现上下文对话



2) 新建会话



提供按钮 New Session



点击后：清空本地显示的消息列表，并把当前 conversation_id 重置为空



下一次发送将触发后端创建新会话并返回新 conversation_id（即“新ID”）



3) 前端本地持久化（A）



localStorage 保存两类数据（用于 UI 展示与复现问题；真实上下文仍以服务端为准）：



chat_history_conversation_id：当前会话ID



chat_history_messages：用于展示的消息数组（仅 UI）



消息结构建议：



{ role: "user"|"assistant", text: "...", ts: Date.now() }





页面刷新后自动恢复：conversation_id + UI消息列表



4) 调试可观测性（A）



页面必须有调试区块，至少包含：



Request JSON（本次请求体：{ user_text, conversation_id? }）



Response JSON（原始响应）



Status（HTTP 状态码、耗时ms）



Error（失败时展示错误信息/响应文本）



5) 输入与发送体验（7B）



只做“按钮发送”（不做快捷键）



发送中禁用按钮，防重复提交



失败时：不要丢失用户输入（至少保留在输入框或消息区），并展示错误信息，允许再次点发送重试



6) 参数开放程度（6A）



严格只用最小字段：user_text、conversation_id



不做高级选项/额外字段



实现细节要求（务实、便于后续扩展）



纯原生 HTML/CSS/JS，不引入框架，不改构建流程



函数拆分清晰（后续方便加“导入conversation_id/多会话列表”等）：



loadState() / saveState()



renderMessages(messages)



setConversationId(id)（同步到 UI 与 localStorage）



buildRequestBody(userText, conversationId)



sendToApi(body)（fetch，返回 {status, ms, json, rawText} 之类结构）



handleSend()（按钮点击主流程）



handleNewSession()



UI 最小布局（建议）



顶部：标题 + 当前 conversation_id 显示（无则显示 “(new)”）



中部：消息列表（user/assistant 两种样式即可）



底部：textarea 输入框 + Send 按钮 + New Session 按钮



侧栏/下方：Debug 面板（Request/Response/Status/Error）



关键行为验收（自测清单）



首次发送：请求不带 conversation_id → 响应返回 conversation_id → 页面显示并持久化



第二次发送：请求带 conversation_id → 回复能引用上一轮（证明上下文生效）



刷新页面：conversation_id 与消息仍在



点击 New Session：UI 清空，conversation_id 变空；下一次发送得到新 conversation_id



后端挂掉/返回非200：页面显示 status/耗时/error，且不崩溃



代码注意点



fetch 使用绝对地址或同源：接口为同域 http://127.0.0.1:8000/api/chat/send（页面同域打开时可用相对 /api/chat/send）



处理非 JSON 响应：先读 text()，再 try JSON.parse；解析失败也要把 raw text 放到 debug



assistant 文本字段按文档：优先读取 assistant_text



按以上要求直接生成代码与文件改动。不要重构现有单次对话页，只新增入口链接。