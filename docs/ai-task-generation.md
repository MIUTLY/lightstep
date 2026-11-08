# 真实AI任务生成与可重试失败

2026-11-07，源于PR #11（039b26f）的独立分支fix/real-ai-task-generation。#11现已合并main（172432ab），#12已改目标为main并按用户本轮授权整合，最终合并记录见[handoff.md](handoff.md)。沿用既有forest_v1，不重做父子切换，也不带入PR #10、前端、轻承诺、回执或手帐改动。

## 运行与提交边界

- app中只有真实OpenAI兼容适配器。LLM_PROVIDER默认openai；mock、不配置密钥/模型/地址不能生成。领域分类仅供摩擦/偏好记录。
- 生成请求使用原始具体目标，而非领域名称或剥掉语义的展示标题。返回严格嵌套trees，先执行既有深度、字段、文本、分支和节点数检查。
- 再向真实AI发起独立内容复核，必须接受且相关性、必要覆盖、父子一致、无重复均为布尔true。复核不合格也失败，不生成替代模板。
- 关键歧义允许返回单个clarification问题，保留原目标及旧任务，回答后再生成并复核。
- SQLite新增task_generation_drafts表，记录每用户最新草稿：generation_id、original_input、goal、answers、status、question、error、updated_at及内部旧任务快照。原始目标与问答不会丢失；API不暴露内部快照。没有重建旧表，不转换/删除旧任务。
- 只有有效森林才在同一事务比较最新草稿ID与原任务完整快照，然后保存森林并替换任务。等待期间用户完成/退出/切换导致快照变化则拒绝覆盖。并发旧生成也不能覆盖更新的草稿。成功替换仍从中档、0步开始，旧day_log不被删除。
- 生成失败只更新草稿，不更新任务、叶子完成集合、偏好、预约、便签或历史，也不提前触发跨天清理。其他接口原有跨天规则未在本轮改动。
- 查看、完成、轻重切换、旧任务兼容读取均使用已有存储；不因AI失败降级或重拆。原step_id保护继续有效。

## 接口

POST /api/chat 保留已有调用方式。空闲时“洗衣服”“洗碗”“整理桌面”可触发生成；已有任务显式“换成洗碗”才替换。步骤提问、记便签、轻重控制不改为新目标。

POST /api/task/generate：`{"user_id":"demo","goal":"具体原始目标"}`。用于任意目标的显式生成或替换，绕过聊天关键词判定。

生成流程返回HTTP 200的Reply，表示请求已处理，**不等于生成成功**。只有generation.status=succeeded才有新任务。generation失败或澄清时state/task仍是旧任务（无旧任务则idle/null），reply是可直接展示的明确中文提示；不会显示“准备好”。现有前端可以按reply显示错误，并按返回task保留旧卡片。

```json
{
  "reply":"AI响应超时，尚未生成新任务。请重试。 原始输入已保留，已有任务和进度不会因此改变。",
  "state":"idle",
  "task":null,
  "buttons":["重试生成"],
  "generation":{
    "generation_id":"服务端生成的ID",
    "original_input":"换成洗碗",
    "goal":"洗碗",
    "answers":[],
    "status":"failed",
    "question":null,
    "error":{"code":"AI_TIMEOUT","message":"AI响应超时，尚未生成新任务。请重试。","retryable":true},
    "updated_at":"本地ISO时间"
  }
}
```

- GET /api/task/generation?user_id=demo：只读返回`{"generation":最新草稿或null}`。/api/session/state和/session/open也附带generation，便于重新打开后恢复失败/澄清提示。
- POST /api/task/generation/retry：`{"user_id":"demo","generation_id":"当前ID"}`。保留原始输入和问答，创建新草稿ID、取最新任务快照后重试。失败或中断停留generating的请求都能重试；已成功/过时ID返回409，不再次替换任务。
- /api/chat输入“重试生成”或“重试”也可重试当前失败/中断草稿，不要求前端先增加按钮路由。
- POST /api/task/generation/answer：`{"user_id":"demo","generation_id":"当前ID","answer":"用洗衣机"}`。仅needs_clarification可回答；其他状态/过期ID返回409。
- 不改前端也可在聊天输入“补充：用洗衣机”，回答当前澄清问题。后端提示中说明该格式；普通聊天不会被隐式吞成答案，轻重/便签/结束等控制保留原行为。专用澄清UI由前端成员接入。

status可为generating、failed、needs_clarification、succeeded；error包含安全code/message/retryable，不含密钥、原始供应商错误体。retryable=true表示允许重试，不表示配置/认证错误能自行恢复。其codes为AI_NOT_CONFIGURED、AI_CONNECTION_FAILED、AI_TIMEOUT、AI_AUTH_FAILED、AI_RATE_LIMITED、AI_SERVICE_FAILED、AI_INVALID_RESPONSE、AI_CONTENT_INVALID、TASK_CHANGED。

普通AI聊天/情绪或步骤问答调用失败通过HTTP 502/503/504及字符串detail提示，另附code/retryable；不伪造AI回复。参数422和过期生成409沿用HTTP错误。/api/health不探测AI。

## 测试与待验收

backend/tests/fakes.py仅供测试显式注入；app、run.py均不导入，不存在环境变量开启的测试生成器。smoke_test.py自动使用临时SQLite并显式注入替身。

后端回归命令：`python -m unittest discover -s . -p 'test_*.py' -v`；流程冒烟：`python smoke_test.py`。具体结果与提交见[handoff.md](handoff.md)。

真实供应商样本、语义复核误判率、网络时延及微信端表现尚未验证。测试里的“洗衣/洗碗/桌面”是隔离的供应商响应数据，只能证明目标传递、结果保存和拒绝路径正确，不能冒充真实AI质量验收。内容复核仍依赖模型判断，不能保证所有自然语言遗漏均被发现。前端成员需要核对回复显示、草稿恢复及专用澄清入口；本轮不修改客户端。
