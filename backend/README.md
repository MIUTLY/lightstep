> 最新流程：完成备忘录一项后自动继续同一清单下一项；最后完成或中途退出成功后回对话页弹出可填写回执，点击保存才写本地手帐。失败不跳页、不假保存。本轮前后端联动规则见[连续专注与回执](../docs/focus-chain-receipts.md)。

> 2026-11-08最新：每项任务独立表现计步，按当前执行号选择正常猫和固定票根；前台300秒未操作只换走神图。公共素材改由后端托管，用户文字/合成图仍仅本地；同日手帐多页追加，底图未提供。预约不恢复、轻承诺仍取消。 接口与分工见[最新素材协议](../docs/task-presentation-assets.md)。

> 最新产品规则：AI拆分用于降低行动门槛，只记录用户自报进度，不检查答案或强加理由/留证/成果验收。生成、范围澄清与计划审核同步遵守，见[行动辅助规则](../docs/action-support.md)。

> 对外文案增加统一过滤：删除明确内部括号说明，保留必要动作与任务约束；父任务动作明细改为自然换行。规则与接入见[展示文案协议](../docs/public-ai-text.md)。

> 最新修复：默认聊天由真实AI区分闲聊、任务和范围补充；任务澄清在对话页完成，focus非空才进入专注。接口字段、失败处理和前端接入见[闲聊与专注前澄清](../docs/chat-and-clarification.md)。

> 新主流程接口：真实AI多任务备忘录、独立森林专注、回执事实与当日完成事件，见[接入协议](../docs/today-memo.md)。默认/chat要求request_id并返回备忘录；前端需按新协议接入。

# 轻步 LightStep · 后端

AI 学习搭子「小步」—— 一只懒洋洋的黑猫，帮你把「动一下」这件事变得不可怕。

> 三个「不」：**不催促、不吓你、不记仇。**

本目录是轻步项目的后端（FastAPI），前端通过 HTTP 接口与「小步」交互。

## 当前进度（2026-11-07）

接手入口：[CODEX_HANDOFF.md](../CODEX_HANDOFF.md)。当前后端取消所有任务计时、预约与无操作召回；未完成跨天保留、整项完成从备忘录移除，回执/手帐仍长期保留。前端需同步删减，详见[最新生命周期协议](../docs/task-lifecycle.md)。

本轮落实前后端分离与数据边界：任务与偏好由后端管理，回执及留言由客户端保存；便签返回状态已修复，其余已知缺陷见交接记录。以下未逐项完成产品验收。

- [当前进度、缺陷与下一轮任务](../docs/handoff.md)
- [需求边界与待定产品规则](../docs/requirements.md)
- [团队与 Codex 协作约定](../AGENTS.md)

已有任务流程和网页调试页；运行只使用真实AI，未配置也可启动服务和操作已有任务，新生成必须配置AI。历史DeepSeek连通测试不代表当前森林协议已完成实测。
任务保护、参数/状态校验、粒度跳步和自然收尾已有修复分支；当前合并状态与剩余任务以交接记录为准。
后续按任务开分支并提交 PR，由另一位队员检查后合并。

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python run.py            # 启动于 http://127.0.0.1:8000
python smoke_test.py     # 显式注入测试替身和临时SQLite的流程冒烟，不验证真实AI
```

默认且唯一支持的提供方是`LLM_PROVIDER=openai`。复制`.env.example`为`.env`并在后端填写真实供应商地址、模型、密钥。缺配置、超时或非法返回明确失败，保留输入和旧任务，不使用模板兜底。`LLM_PROVIDER=mock`也不能生成任务。详见[生成与重试协议](../docs/ai-task-generation.md)。

## 核心能力

### 1. 用户主动调整步骤

新任务以[三层任务森林](../docs/task-forest.md)保存轻/中/重对应关系，默认第一个中任务。主动调整逐档选对应父/子节点，切换不算完成。手动完成当前范围才消费剩余叶子，部分完成的父任务只要求剩余内容；一次生成后不重新请求AI。

取消耗时测量、快慢阈值、耗时摩擦记录与自动调档；新旧任务都保持用户选择的档位。旧三清单和_step_plan有序队列继续兼容，不猜测转换。

### 2. 两段式情绪提示
先识别情绪（焦虑 / 低落 / 正常 / 亢奋），再决定回复语气；接真 LLM 时拆成两次调用。

### 3. 三层记忆
- **任务级**（未完成跨天保留）：当前任务、当日记录
- **偏好级**（长期）：摩擦地图、跨天交接
- **便签**：沿用已有服务端实现；预约提醒已停用；私人手帐与回执在客户端保存

### 4. 摩擦地图（个人化）
按领域（写作 / 背单词 / 阅读 / 代码 / 运动 / 收拾）沉淀「哪里容易卡」。做某类任务常卡时，下次自动拆得更细，不点破、不记仇，只说一句「这类任务之前容易卡，我先拆得细一点」。

### 5. 跨天温柔交接
未开始和执行中的任务都跨天保留；重新打开保留原节点、档位与完成部分，不自动推进或重启已结束的专注。整项完成即从备忘录移除。

### 6. 私人静默手帐
回执和私人留言由客户端本地生成与保存，不再在完成/退出任务时自动写入服务器。旧手帐接口返回410；旧数据库中已有表不自动删除。网页调试页提供主动保存的本地文本手帐，小程序图片手帐待前端接入。

### 7. 5 件小事
换件小事、发呆、今天什么都不想干、走神记笔记、温柔收尾 —— 都只轻轻接住，不评判。

完整收尾表达可结束当前任务；“我累了”会保留进度并给出结束/拆小选择。否定、条件、提问或便签中的结束文字不会仅因包含关键词而退出。常用规则及识别边界见[接口说明](../docs/api.md)。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/session/open` | 打开会话 / 每日问候 |
| POST | `/api/chat` | 自由对话（意图识别入口） |
| POST | `/api/task/choose_time` | `now/not_today`；预约值已停用并返回410 |
| POST | `/api/reminders/poll` | 已停用，返回410 TASK_TIMERS_REMOVED |
| POST | `/api/task/commit` | 普通开始确认 `agree=true/false`，无计时 |
| POST | `/api/step/complete` | 手动完成一步；duration_ms可省略，旧值忽略 |
| POST | `/api/step/resize` | 太重了/太简单 `smaller/bigger` |
| POST | `/api/task/exit` | 温柔收尾 |
| POST | `/api/note` | 走神记笔记 |
| POST | `/api/handoff/resume` | 接着上次做 |
| POST | `/api/handoff/dismiss` | 翻篇 |
| GET | `/api/journal` | 已停用，返回410 |
| POST | `/api/journal/add` | 已停用，不接收留言，返回410 |
| DELETE | `/api/journal/{id}` | 已停用，返回410 |
| GET | `/api/session/state` | 当前状态 |
| GET | `/api/history` | 历史 |
| GET | `/api/daily/summary` | 今日小结 |

## 目录结构

```
backend/
├── app/
│   ├── config.py        # 配置（.env 覆盖）
│   ├── schemas.py       # 请求/响应模型
│   ├── db.py            # SQLite 存储
│   ├── persona.py       # 小步人设文案
│   ├── decompose.py     # 仅领域识别，不生成任务
│   ├── granularity.py   # 主动粒度切换辅助
│   ├── step_plan.py     # 旧任务有序队列兼容
│   ├── task_forest.py   # 新任务三层森林、剩余内容与叶子进度
│   ├── prompts.py       # LLM 提示词
│   ├── llm.py           # Mock / OpenAI 兼容 LLM
│   ├── services.py      # 核心编排
│   └── main.py          # FastAPI 路由
├── run.py
├── smoke_test.py
└── requirements.txt
```

## 理论背书

设计背后的心理学依据见 [`docs/理论背书.md`](../docs/理论背书.md)（实施意图、BJ Fogg 行为模型、行为激活、蔡格尼克效应、自我慈悲等）。

## 分离部署与验证

配置 LIGHTSTEP_HOST、LIGHTSTEP_PORT、LIGHTSTEP_CORS_ORIGINS；API 独立部署可关闭 LIGHTSTEP_SERVE_DEBUG_UI，部署时关闭 LIGHTSTEP_RELOAD。GET /api/health 提供存活检查。完整说明见 [部署说明](../docs/deployment.md)、[数据边界](../docs/architecture.md)和[接口约定](../docs/api.md)。

后端边界回归：python -m unittest -v test_storage_boundary.py。
本地手帐回归：node --test test_local_journal.cjs。

## 真实AI检测

接入步骤和本次实测结果见 [AI接入说明](../docs/ai-integration.md)。服务端设置模型地址、名称及密钥后，运行 python check_llm.py；加 --task 额外验证任务森林生成与语义复核（两次请求）。不使用离线兜底，失败会返回非零退出码。默认示例使用 deepseek-flash、LLM_THINKING=disabled、LLM_MAX_TOKENS=1024；三层拆分单独使用LLM_DECOMPOSE_MAX_TOKENS=4096。使用其他供应商时按其协议修改，密钥不入库。

模型回归检查：python -m unittest -v test_llm.py test_storage_boundary.py。

后端回归（backend目录、显式注入测试替身及独立临时数据库）：

```bash
python -m unittest discover -s . -p "test_*.py" -v
python smoke_test.py
```

本轮测试结果见[最新交接](../docs/handoff.md)，覆盖AI失败/重试/澄清及旧森林、旧队列、参数、情绪收尾、存储边界、计时停用、完成移除和跨天保留回归。前端/网页静态文件本轮未修改，前端行为由对应成员验收。

本轮切换协议为嵌套trees，check_llm.py --task验证真实森林输出（不允许离线冒充）。本轮只跑了显式注入的测试替身/模拟供应商回归，未使用真实密钥或声称新协议已完成供应商语义验收。
