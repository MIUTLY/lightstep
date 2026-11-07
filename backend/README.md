# 轻步 LightStep · 后端

AI 学习搭子「小步」—— 一只懒洋洋的黑猫，帮你把「动一下」这件事变得不可怕。

> 三个「不」：**不催促、不吓你、不记仇。**

本目录是轻步项目的后端（FastAPI），前端通过 HTTP 接口与「小步」交互。

## 当前进度（2026-11-07）

本轮落实前后端分离与数据边界：任务与偏好由后端管理，回执及留言由客户端保存；便签返回状态已修复，其余已知缺陷见交接记录。以下未逐项完成产品验收。

- [当前进度、缺陷与下一轮任务](../docs/handoff.md)
- [需求边界与待定产品规则](../docs/requirements.md)
- [团队与 Codex 协作约定](../AGENTS.md)

已有离线任务流程和网页调试页；DeepSeek真实调用及项目任务创建已验证；对话质量、小程序联调与部署仍待验证。
优先处理跳步、便签状态不一致、提问覆盖任务、参数校验和模型异常兜底。
后续按任务开分支并提交 PR，由另一位队员检查后合并。

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python run.py            # 启动于 http://127.0.0.1:8000
python smoke_test.py     # 跑一遍全流程冒烟测试（离线、无需 key）
```

默认 **离线模式**（`LLM_PROVIDER=mock`）：任务拆解用预设模板、情绪用规则识别，无需任何 API key 即可跑通全流程。接真 LLM 时复制 `.env.example` 为 `.env`，改 `LLM_PROVIDER=openai` 并填 key 即可（OpenAI 兼容，DeepSeek / 豆包 / OpenAI 均可）。

## 核心能力

### 1. 自适应步骤粒度
用户每完成一小步都会回传耗时：
- 做得快（< 15s）→ 状态在线，下一步**加量**
- 卡得久（> 90s）→ 启动吃力，下一步**拆细**
- 中间 → 保持

三档粒度：细 / 中 / 粗。切换时按完成比例映射进度，不让人从头再来。

### 2. 两段式情绪提示
先识别情绪（焦虑 / 低落 / 正常 / 亢奋），再决定回复语气；接真 LLM 时拆成两次调用。

### 3. 三层记忆
- **任务级**（当天清空）：当前任务、当日记录
- **偏好级**（长期）：摩擦地图、跨天交接
- **便签与提醒**：沿用已有服务端实现；私人手帐与回执在客户端保存

### 4. 摩擦地图（个人化）
按领域（写作 / 背单词 / 阅读 / 代码 / 运动 / 收拾）沉淀「哪里容易卡」。做某类任务常卡时，下次自动拆得更细，不点破、不记仇，只说一句「这类任务之前容易卡，我先拆得细一点」。

### 5. 跨天温柔交接
任务做了一半没关，第二天打开时不会硬清零，而是轻轻问一句：「上次你写到「X」。想接着就接着，不想就翻篇。」

### 6. 私人静默手帐
回执和私人留言由客户端本地生成与保存，不再在完成/退出任务时自动写入服务器。旧手帐接口返回410；旧数据库中已有表不自动删除。网页调试页提供主动保存的本地文本手帐，小程序图片手帐待前端接入。

### 7. 5 件小事
换件小事、发呆、今天什么都不想干、走神记笔记、温柔收尾 —— 都只轻轻接住，不评判。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/session/open` | 打开会话 / 每日问候 |
| POST | `/api/chat` | 自由对话（意图识别入口） |
| POST | `/api/task/choose_time` | 选择开始时间 `now/later/not_today` |
| POST | `/api/task/commit` | 5 分钟轻承诺 `agree=true/false` |
| POST | `/api/step/complete` | 完成一小步（带 `duration_ms`） |
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
│   ├── decompose.py     # 离线拆解 + 情绪识别 + 领域识别
│   ├── granularity.py   # 自适应粒度引擎
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

接入步骤和本次实测结果见 [AI接入说明](../docs/ai-integration.md)。服务端设置模型地址、名称及密钥后，运行 python check_llm.py；加 --task 额外验证一次任务拆解。不使用离线兜底，失败会返回非零退出码。默认示例使用 deepseek-flash、LLM_THINKING=disabled、LLM_MAX_TOKENS=1024。使用其他供应商时按其协议修改，密钥不入库。

模型回归检查：python -m unittest -v test_llm.py test_storage_boundary.py。
