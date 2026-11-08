> 最新跟进：主页白屏已由主线 PR #29 修复，本分支保留 PR #30 布局/票根改动，补齐轻重按钮 transitionBusy.value、失败提示与回执按需挂载。分支 fix/chat-homepage-load，基线 cc5f8ae，实施 650dc1af2201576aeb0d3ab1a368a2025e9a97ef。59项Node、4项真实微信编译产物检查及官方uni-app 5.36构建通过；未做微信设备验收，尚未合并/部署。详见[交接](docs/handoff.md)与[修复报告](docs/change-reports/2026-11-08-homepage-resize.md)。下方为历史记录（PR #28已合并）。

> 最新修复：独立备忘录任务自动连续，最后完成/成功中断后回对话弹可填写回执，用户主动保存才写本地手帐。用户本轮授权前端修改；分支fix/focus-chain-and-receipts，实施e094e6495750cc6de338f51dc3a4ae7811db7d0a。190项后端、47项Node、隔离冒烟和三个SFC通用编译检查通过，微信真机/HBuilderX未验收；未合并/部署。根因、接口、文件、旧测试替代及限制见[focus-chain-receipts](docs/focus-chain-receipts.md)和[handoff](docs/handoff.md)。

> 2026-11-08最新：feat/task-presentation-assets基于主线332e192，实施3db389dbd2ab764d4b05b9e8ddc76a662eb70b03。每项独立表现计步、确定性猫/票根、后端30张运行图和状态原包托管/保留、前台300秒仅换走神图协议；186项回归及隔离冒烟通过。队友现有前端/JSON兼容补丁保持，前端新策略与微信验收仍待接入。原票根大包上传中断，未入仓，在/workspace/deliverables/lightstep-original-receipts.zip保留；线上运行不依赖它。底图未提供，不造替代。接口与限制见[task-presentation-assets.md](docs/task-presentation-assets.md)及[handoff](docs/handoff.md)。本轮未合并/部署。

> PR #17追加产品语义修正：AI只拆可执行行动、记录用户自报进度，不检查答案/正确率，不强加理由、留证、自评或质量验收。共享政策用于生成、审核和范围澄清，已有完成接口不评分；用户原目标必要的检查/论证/交付仍保留。实施e9f6fd5a52042bc2ab986a99ef36dc9efdbf8db2，164项回归及4项专项、隔离冒烟通过。新规则用于新生成，不重拆旧森林丢进度；真实AI样例与微信端未验收。详见[action-support](docs/action-support.md)和[handoff](docs/handoff.md)。未合并/部署。

> 最新任务：统一过滤对外AI展示文案，去掉明确内部括号/思考标签，保留任务约束与实际动作。实施3b1ba659887427d32bde796620f6cbc6aeefd917，160项回归与隔离冒烟通过；接口字段/身份/存储不变，仅展示投影。见[public-ai-text.md](docs/public-ai-text.md)与[handoff](docs/handoff.md)。本轮未改前端，未合并/部署；微信排版和真实供应商输出待验收。

> 最新修复：真实AI闲聊分流、对话页澄清任务范围后才进入专注，实施9ceb962eb02a75a166fbc93cf0ae7fc8008d467e；153项回归、8项最终专项和隔离冒烟通过。前端必须focus非空才跳转，专注页不保留常规询问输入。最新主线.env.example疑似密钥已在分支恢复为空，请维护者轮换旧密钥。本轮只改后端与文档，未合并/部署。接口见[对话与澄清](docs/chat-and-clarification.md)，完整测试/剩余项见[handoff](docs/handoff.md)。

> 最新任务（2026-11-07）：取消全部任务计时，未完成跨天保留，整项完成移出备忘录；回执/手帐长期保留。本轮独立分支refactor/manual-task-lifecycle，实施[5cd6a1e7c5a148976d443be39bb148c577a7ef89](https://github.com/MIUTLY/lightstep/commit/5cd6a1e7c5a148976d443be39bb148c577a7ef89)；145项后端回归与隔离冒烟通过。#10已因产品取消而关闭（未合并，分支保留）。前端计时/UI删除、日期恢复和本地保存仍待队友接入。接口见[task-lifecycle.md](docs/task-lifecycle.md)，变更、测试与未验证项见[handoff.md](docs/handoff.md)。本轮尚未合并或部署。

> 最新：feat/focus-capture补齐专注桌宠新增任务的后端接口，真实AI位置识别、缺失/同名澄清、批次去重与会话保护。实施e2ccd906774261b25db51563a9d05dcfab2d0d7c，144项回归及隔离冒烟通过。前端桌宠/双击/气泡/侧边栏拦截和微信计时仍待对应成员实施验收。接口见[focus-capture.md](docs/focus-capture.md)，记录见[handoff.md](docs/handoff.md)。新PR不自动合并。

> 最新任务：feat/today-memo实现后端今日多任务清单、独立森林专注和回执/手帐事实，代码96c414ba21ddac4b4cb4e4083eeab4c433490c92，126项回归及隔离冒烟通过。默认/chat协议已变化，前端需接入[today-memo.md](docs/today-memo.md)；真实AI样本及微信UI未验收。新PR不自动合并，#10继续独立。详见[交接](docs/handoff.md)。

> 本轮合并状态（2026-11-07）：用户明确授权按#11→#12整合后端。#11已合并main，提交172432ab871ef5017587fa8a6dccbe89d57068eb；#12目标已改为main，本说明随其进入主线，最终merge SHA见[PR #12](https://github.com/MIUTLY/lightstep/pull/12)。已验证业务快照07e00747c5ee3071afc39a2c67265dae6294ce15（105项回归及隔离冒烟通过），业务实施bbe6f60。#10保持草稿，微信验收未完成；真实AI样本和微信端显示仍待验收，不因合并视为通过。详见[合并交接](docs/handoff.md)。下文为历史实施记录，旧“未合并/目标feat/task-forest”状态已更新。

> 最新后端任务（2026-11-07）：运行只支持真实AI，已取消离线/领域模板和两层静默降级。独立分支fix/real-ai-task-generation，基于未合并PR #11的039b26f；本修复PR先以feat/task-forest为base。实施提交[bbe6f60b4b9e0a44f5816e5b643b0a3d35e7de62](https://github.com/MIUTLY/lightstep/commit/bbe6f60b4b9e0a44f5816e5b643b0a3d35e7de62)。105项后端回归、隔离冒烟和无密钥真实进程失败流程通过；真实供应商样本和微信显示未验收。未修改前端/计时/回执/手帐。重试、澄清、业务失败HTTP 200语义见[生成协议](docs/ai-task-generation.md)，详情见[最新交接](docs/handoff.md)。后文为历史上下文，旧mock运行约定已失效。

> 最新后端任务（2026-11-07）：用户已确认三层父子任务森林、默认中档、按最小叶子保留完成进度。独立分支feat/task-forest，基于main 7f75a7d；实施提交c405a78d2b4c7b3a8b1fbc15ba58aacef836fd41。只改后端和协议/交接文档，未带入PR #10的计时及前端改动。详见[任务森林协议](docs/task-forest.md)和[最新交接](docs/handoff.md)。84项后端回归及mock冒烟通过，真实模型语义质量与前端联调未验收。

> 2026-11-07追加：用户已明确授权合并PR #8；上一轮草稿限制已更新，未完成验收项仍保留。以[最新交接](docs/handoff.md)及[PR实际合并状态](https://github.com/MIUTLY/lightstep/pull/8)为准。

# 轻步 LightStep：交给 Codex 的开发说明

> 接手后更新（2026-11-07，北京时间）：已通过GitHub重新核对，#4/#5/#7已合入main，重复#6已关闭；#8现以main为目标且仍是草稿。本文下方PR依赖表是交接时历史快照，不再代表当前状态。
>
> 本轮继续在fix/start-reminder-options修复预约消费后停表、同页改约重启、隐藏再显示的请求竞争、过时状态查询与轮询错误提示；新增22项Node和2项后端回归。实施提交：20b3222062cf3e2eb8fee0c9747e8a03b87406ee。验证及待定项以[最新交接](docs/handoff.md)和[本轮报告](docs/change-reports/2026-11-07-start-reminder-polling.md)为准。仍未合并或部署，勿扰/提醒可靠送达及微信验收未完成。

更新日期：2026-11-07（北京时间）。这是交接时的状态快照，接手后先查询远端分支和PR，不能假定它们仍未合并。

## 一、项目与已经确认的决定

- 仓库：<https://github.com/MIUTLY/lightstep>，私有仓库，前后端在同一个项目仓库，不再分别建立后端仓库。
- 产品：微信小程序里的AI学习搭子“小步”，把用户目标拆成眼前一小步。不催促、不吓人、不追究退出；默认只显示当前一步。
- 技术：frontend/为队友提交的uni-app/Vue小程序源码；backend/为FastAPI + SQLite；backend/static/只是网页调试页，不能当成微信小程序成品。
- 用户已确认采用前后端分离。原策划中的“不需要真后端、全部本地保存”已被后续技术决定替代。
- 后端管理任务、步骤进度、偏好、摩擦地图和当前已有的走神便签/提醒。前端只缓存展示，不独立推进任务。
- 回执图片、写给自己的私人留言和手帐索引仅由客户端主动保存；不上传、不分析、不自动生成服务器手帐。走神便签与回执留言是两类数据。
- 用户已经安装微信开发者工具；尚未确认其本地项目成功编译或连上后端。开发阶段可用用户电脑运行后端，尚未部署云服务器或稳定公网服务。

权威入口：AGENTS.md、docs/requirements.md、docs/architecture.md、docs/api.md、docs/handoff.md。需求来自用户最新版策划文本《粘贴的文本 (1).txt》及后续确认。部分早期README仍写“前端占位”，已过时，应以实际源码和最新交接为准。

## 二、代码在哪里：已合并与未合并必须分开

交接时main为`0d217753fd64274177d9443928c3a7f8cd1cd77b`。

| PR | 内容 | 交接时状态 |
| --- | --- | --- |
| [#1](https://github.com/MIUTLY/lightstep/pull/1) | 前后端职责、数据边界、部署配置、本地手帐边界 | 已合并 |
| [#2](https://github.com/MIUTLY/lightstep/pull/2) | DeepSeek接入、真实检测、模型结构校验与兜底 | 已合并 |
| [#3](https://github.com/MIUTLY/lightstep/pull/3) | 队友提交完整uni-app前端工程 | 已合并 |
| [#4](https://github.com/MIUTLY/lightstep/pull/4) | 当前任务保护、参数与状态校验 | 未合并；目标main |
| [#5](https://github.com/MIUTLY/lightstep/pull/5) | 粒度调整不跳步、稳定步骤标识 | 未合并；目标#4的分支 |
| [#7](https://github.com/MIUTLY/lightstep/pull/7) | 自然收尾与疲惫反馈、防止误退 | 未合并；目标#5的分支 |
| [#6](https://github.com/MIUTLY/lightstep/pull/6) | 与#7相同head分支，目标为main | 重复审查入口，包含前置修复；不要按独立功能再合一次 |
| [#8](https://github.com/MIUTLY/lightstep/pull/8) | 本次5/10分钟预约进行中修改与完整交接说明 | 草稿，目标#7的分支；不能直接视为验收完成 |

推荐保留增量审查顺序：#4合入main → 把#5目标改为main后审查合并 → 把#7目标改为main后审查合并。#6与#7二选一处理，建议核对后关闭重复的#6。本文未执行任何合并或关闭。

分支与交接时远端head：

| 分支 | head |
| --- | --- |
| fix/task-intent-and-validation | 8bd7c4e0f7956330098cf988f155d3c3e3c10a34 |
| fix/preserve-step-sequence | 1b0e4ecc562d0aecbce2825016d2a70be6d8583f |
| fix/natural-task-ending | 716057a29c92b2336089841999c190cb55146303 |
| fix/start-reminder-options | 本次交接草稿分支，基于上一行，含下面的预约进行中修改及本文 |

**只拉main会缺少#4/#5/#7修复。接着当前工作时切到fix/start-reminder-options，先核对草稿PR与最新远端状态。不要把这些分支当成独立、互不依赖的改动直接覆盖。**

## 三、已经改了什么、为什么这样改

| 模块 | 实际改动 | 依据与原因 |
| --- | --- | --- |
| 项目结构 | 同仓库frontend/backend/docs，补技术边界、协作与部署说明 | 方便成员按职责开发，目录并不隔离GitHub写权限 |
| 服务部署 | 增加监听/端口/CORS/调试页配置及/api/health，支持独立API服务 | 小程序通过HTTP访问后端，GitHub不会自动运行服务器；CORS不等于身份认证 |
| 手帐边界 | 停止服务器自动保存回执，旧/api/journal*返回410；旧journal表与数据不自动删除 | 用户确认回执与私人留言留在客户端；网页调试页提供本地文本示例 |
| B02便签 | 返回当前真实state/task，不再把执行中的任务误报为idle | 避免前端按错误状态切页面 |
| AI接入/B06 | 兼容DeepSeek等接口，输出上限/JSON约束/超时与异常兜底；拒绝空列表、非文本步骤、非法结构和截断输出；check_llm.py真实检测不允许mock冒充 | 防止坏输出进入任务状态机，区分离线可跑与真实AI可用 |
| B03任务保护 | 普通提问不覆盖目标；明确“换成背单词”才替换；只说“换个任务”询问目标并保留进度；新目标生成成功后再替换 | 提问、含糊表达不代表放弃旧任务 |
| B04/B05校验 | 非空文字、严格布尔、非负整数耗时、枚举；非法参数422、非法状态409，先校验再写入 | 防止负耗时、未开始完成、when拼写错误导致误删任务等问题 |
| 状态一致性 | ready/committing阶段拆小不自动开始；拒绝承诺返回真实ready状态 | 页面必须按服务器真实状态导航 |
| B01粒度 | 新任务以normal清单建有序动作队列，粗档合并相邻动作，细档保守拆当前动作并保留剩余；移除不同清单间的百分比映射 | 完成“打开单词本”后不能跳过学习直接标记生词；已完成前缀不重复、待做内容不丢失 |
| 步骤计时 | TaskView增加step_id，uni-app及调试页优先按稳定标识计时 | 两个不同动作可能文字相同，不能累计到上一步耗时；step_id不是请求幂等键 |
| 完成文案 | 只表示“这一小段先到这”，不声称整个大目标完成 | 当前拆解可能只是启动小段，不证明“背50个词”等总目标已全部覆盖 |
| B07收尾 | 完整明确表达直接结束；“我累了”保留进度并提供结束/拆小；否定、条件、引用、便签和问题不因含“结束”而误退 | 用户自主结束；疲惫本身不代表确认删除任务。采用常用分句规则，未覆盖全部自然语言 |

AI真实连通曾在此前轮次完成：供应商/models、最小聊天及项目/api/chat的真实情绪识别+拆解均成功。当前只支持真实AI，默认openai；此前默认mock已取消，未保证用户电脑已配置持续可用的真实AI环境，也没有已上线后端。密钥不在本文，不能从聊天历史复制进源码；应由用户更换曾公开过的密钥，放后端环境配置。

详细修改依据见docs/change-reports/下的task-flow、step-sequence、natural-ending三份记录。

## 四、本次预约修改：进行中，交给下一位完成验收

分支：fix/start-reminder-options；基线为fix/natural-task-ending的716057a。用户中途要求交接，因此本轮以草稿保存，不标为功能已全面完成。

接手入口：[草稿PR #8](https://github.com/MIUTLY/lightstep/pull/8)；初始保存提交：[76c1187](https://github.com/MIUTLY/lightstep/commit/76c118710fffa511add8113513338b700ebad552)。后续文档提交同在该分支。

已经写入代码：

- ChooseTimeRequest新增`in_5_minutes`、`in_10_minutes`；ready状态按钮给出“现在开始/5分钟后/10分钟后/今天不做”。旧`later`只询问选5还是10，不再悄悄创建半小时预约。
- SQLite新增task_start_reminders表，每个用户最多一个当前任务预约；保存UTC秒精度到期时间。TaskView新增start_due_at；原有任务表/旧数据不迁移覆盖。
- 改约替换旧预约；开始、退出、换任务、跨天沿用的任务清理会一并取消预约；拆小或疲惫反馈不取消预约。
- 新增POST /api/reminders/poll及客户端API封装；打开会话也会检查到期。取出与标记在同一SQLite事务中，预约最多返回一次，不自动切到开始或执行状态。
- 旧半小时任务提醒的已知文案不再展示，旧reminders行保留，通用提醒仍沿用旧行为。
- uni-app新增前台检查工具；对话页onShow启动、onHide/onUnload停止，每15秒检查；增加5/10分钟按钮映射。通过操作版本与可见性检查，避免开始/退出后旧轮询响应恢复旧任务。
- 网页调试页增加5/10分钟按钮映射，但**尚未加入持续前台轮询**，目前靠重新打开页面检查到期。

必须接着检查的边界：

1. 新增前端轮询工具、session集成和页面生命周期还没有行为回归测试，只有语法检查。需要模拟隐藏/卸载、慢网、多次onShow、请求重叠、提前开始/退出/改约时旧响应返回。
2. 当前start_due_at在提醒已取出后仍可能保留，因此前端会继续无效轮询；应明确“待提醒”标识或消费后的停止条件。
3. 取出即标记notified，响应丢失或客户端因操作变化丢弃响应时，提醒可能未展示；目前没有展示确认/重投协议。最多返回一次不等于可靠送达。
4. 勿扰与预约提醒的关系尚未统一；原有勿扰针对无操作召回，不能宣称预约也已遵守勿扰。
5. 新增预约取出做了局部并发保护，不代表全部任务写操作已有幂等、版本校验或并发安全。
6. 完善对应接口文档、实际微信编译与真机验收后，才能将草稿视为可合并功能。

## 五、还要改什么：建议按顺序做

| 优先级 | 待办 | 验收要点 |
| --- | --- | --- |
| P0 | 核对PR依赖与当前分支，收拢待合并修复 | 避免漏掉#4/#5/#7，或将重复#6/#7当两次功能合并；先审查再合并 |
| P0 | 完成本轮预约前端测试与交互验收 | 5/10分钟准确、改约覆盖、不重复、取消后不提醒、隐藏不轮询、到点不自动开始 |
| P0 | 修复小程序回执/手帐仍请求已停用服务器接口 | 当前frontend/pages/receipt、journal及相关工具需逐项核对；改为本地持久图片+索引，主动保存、失败不假报成功，留言不上传 |
| P0 | 用户本机微信编译与前后端联调 | 测试用显式注入替身、实际运行用真实AI；获取第一条实际报错；区分编译失败、地址不可达和模型超时 |
| P1 | 五分钟轻承诺到期/续时 | 后端当前仍主要是提示与状态；检查已有useFiveMinuteAnchor实际接线，不把组件存在当全链路完成；切后台是否计时待用户决定 |
| P1 | 写操作幂等与任务版本 | 防连点/网络重试重复推进，拒绝旧页面操作新任务；step_id不能代替幂等令牌 |
| P1 | 前后端超时预算 | 现前端35秒、后端单次模型默认30秒，建任务可能串行两次；调整总预算、错误提示及取消/重试策略 |
| P1 | AI任务质量和普通问题回复 | 保证启动步骤具体；测试否定、复合目标和复杂措辞；不能只凭结构校验宣称语义正确 |
| P1 | 演示部署 | 需要稳定异地联调时再部署Python服务，持久保存SQLite，配置HTTPS与小程序网络要求；尚未买服务器/部署 |
| P2 | 清理过时README、接口注释和展示差异 | 已有前端、服务端手帐停用等事实应一致；顺手改文档不能擅自决定产品规则 |

不要自动补建账号、多设备同步、排行榜、连续天数、积分或推送。当前user_id只是演示身份，正式多人开放前另行设计身份归属，不能把它当认证。

## 六、需要用户决定的产品问题

以下策划存在冲突，当前沿用既有行为，不由Codex自行拍板：

- 退出是直接清空还是二次挽留；目前采用直接收尾，不新增挽留。
- 跨天是否提昨天、如何恢复与清理；历史入口是否存在、当天日志保留多久。
- 轻承诺的五分钟切后台是否累计，与无操作召回同时触发时怎么办。
- 执行页最终按钮布局、猫姿态数量、回执/手帐交互细节。

发现冲突先说明选项与影响；继续做不依赖决定的工作。不要以“修bug”为由偷偷删除旧journal/day_log或改变保留策略。

## 七、验证记录与接手命令

交接前本地验证（独立临时SQLite、mock，无真实AI调用）：

- 后端56项unittest通过：原有44项 + 本轮预约12项；覆盖任务保护、输入/状态拒绝、粒度顺序、自然收尾、模型结构、存储边界和预约生命周期。
- Node的6项既有逻辑测试通过：步骤身份3项 + 网页本地手帐3项。**不包含新增预约前端行为测试。**
- frontend/store/session.js、api/index.js、utils/startReminderPoller.js、backend/static/app.js以及chat.vue的script段语法通过；不等于Vue模板、WXSS或微信构建通过。
- mock smoke_test.py通过；没有真实微信编译、真机、线上服务或全流程视觉验收。

建议在自己的克隆中运行（不要沿用本次会话临时路径）：

```bash
git fetch origin
git switch fix/start-reminder-options
cd backend
python -m venv .venv
# 激活环境后：
pip install -r requirements.txt
# 测试显式注入替身；LIGHTSTEP_DB 指向独立测试数据库
python -m unittest -v test_start_reminders.py test_ending_intent.py test_step_plan.py test_task_flow.py test_llm.py test_storage_boundary.py
python smoke_test.py
```

仓库根目录：

```bash
node --test frontend/tests/stepIdentity.test.mjs backend/test_local_journal.cjs
git diff --check
```

uni-app源码需通过HBuilderX编译到微信小程序，再交给微信开发者工具；不是把Vue源码仓库根目录直接当原生小程序导入。详细步骤见docs/local-development.md。后端默认127.0.0.1:8000；手机上的127.0.0.1指手机本身，真机应使用可达电脑IP或部署地址。

## 八、用户对接下来开发的要求

按任务开功能/修复分支、提交PR，不直接覆盖main；保留队友已有前端和非本轮文件。每轮完成后向用户说明：改了什么、依据什么需求或复现问题、为什么这样改、运行了哪些有效检查、还没验证什么；同步docs/handoff.md。

不要在源码、示例配置、PR正文或日志里复制真实密钥，不提交数据库、缓存、node_modules、虚拟环境或小程序私有配置。此轮没有修改模型配置文件；不能因文档提到真实AI实测就假定已获得持续可用密钥。

建议接手后的第一条回复：先复述实际分支/PR状态和最近一轮未验收项，给出本轮要完成的一个明确任务，再动代码。无需重做已通过的功能，也不要把当前草稿直接当成已完成并上线。
