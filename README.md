# 轻步 LightStep · 后端

AI 学习搭子「小步」—— 一只懒洋洋的黑猫，帮你把「动一下」这件事变得不可怕。

> 三个「不」：**不催促、不吓你、不记仇。**

本仓库只做后端（FastAPI），前端通过 HTTP 接口与「小步」交互。

## 当前进度（2026-11-07）

本次同步保留队友原始业务源码，尚未修复已发现的流程问题；以下核心能力描述的是现有实现，并不代表全部通过验收或已与新版策划统一。

- [当前进度、缺陷与下一轮任务](docs/handoff.md)
- [需求边界与待定产品规则](docs/requirements.md)
- [团队与 Codex 协作约定](AGENTS.md)

已有离线任务流程和网页调试页；真实模型效果、小程序联调与部署尚未验证。
优先处理跳步、便签状态不一致、提问覆盖任务、参数校验和模型异常兜底。
后续按任务开分支并提交 PR，由另一位队员检查后合并。

## 快速开始

```bash
cd lightstep-backend
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
- **情感级**（很轻）：便签、提醒、私人手帐

### 4. 摩擦地图（个人化）
按领域（写作 / 背单词 / 阅读 / 代码 / 运动 / 收拾）沉淀「哪里容易卡」。做某类任务常卡时，下次自动拆得更细，不点破、不记仇，只说一句「这类任务之前容易卡，我先拆得细一点」。

### 5. 跨天温柔交接
任务做了一半没关，第二天打开时不会硬清零，而是轻轻问一句：「上次你写到「X」。想接着就接着，不想就翻篇。」

### 6. 私人静默手帐
完成任务 / 结束一天时，自动生成一份安静的「回执」，只自己看，随时可删，也可以手写补充。

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
| GET | `/api/journal` | 手帐列表 |
| POST | `/api/journal/add` | 手帐新增 |
| DELETE | `/api/journal/{id}` | 手帐删除 |
| GET | `/api/session/state` | 当前状态 |
| GET | `/api/history` | 历史 |
| GET | `/api/daily/summary` | 今日小结 |

## 目录结构

```
lightstep-backend/
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
├── docs/理论背书.md      # 背后的心理学理论
├── run.py
├── smoke_test.py
└── requirements.txt
```

## 理论背书

设计背后的心理学依据见 [`docs/理论背书.md`](docs/理论背书.md)（实施意图、BJ Fogg 行为模型、行为激活、蔡格尼克效应、自我慈悲等）。
