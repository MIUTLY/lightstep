# 最新交接：任务保护与校验修复

日期：2026-11-07。基线main：0d217753fd64274177d9443928c3a7f8cd1cd77b。分支：fix/task-intent-and-validation。

当前PR #1、#2均已合并；下方关于“未合并”的文字为当时历史。队友已新增uni-app前端，本轮保留其全部文件，不改前端业务代码或模型配置。

## 改了什么、为什么

- B03：普通问题不再因“写/做/想”等关键词创建或覆盖任务。只有明确换任务命令才替换；询问换什么时保留原任务。依据是已确认的当前任务保护约束。
- B04/B05：严格校验枚举、非负整数耗时、JSON布尔和非空标识/文字；非法参数422，非法动作状态409，校验前不执行数据库写入。依据是已复现的负耗时、未开始完成、非法when删除任务等问题。
- 拆小保持ready/committing/executing原状态，拒绝承诺的响应与数据库状态一致。依据是前端按返回state导航，不能误进执行页。
- AGENTS.md加入每轮说明改动、修改依据、验证和未完成项的要求。

详见 [本轮修改依据](change-reports/2026-11-07-task-flow.md)；接口约定已更新。前端现有409/422错误处理可接收新响应；尚未做实际微信联调。

## 测试与交接

- 24项Python回归、3项Node回归、独立临时数据库上的离线smoke_test.py通过；无真实模型调用。
- 修改文件：backend/app/services.py、schemas.py、main.py、persona.py，新增backend/test_task_flow.py；更新AGENTS.md、docs/api.md、handoff.md；新增本轮报告与local-development.md。
- 实施提交：[ee53e54](https://github.com/MIUTLY/lightstep/commit/ee53e54693f1a76def4f80b466d6adf678935084)；[PR #4](https://github.com/MIUTLY/lightstep/pull/4)。
- 用户追加询问服务器联调：开发可用本地电脑，默认127.0.0.1不适用于手机访问电脑；原理与排查见 [本地联调](local-development.md)。未获得报错，尚不能判定实际故障。

## 后续重点

B01粒度跳步、B07结束意图、5/10分钟预约、手帐客户端迁移、真机联调与并发幂等仍未完成。前端源码已提交，但其手帐仍请求停用接口；本轮没有将此问题标为已修复。

---

# 最新交接：真实AI接入验证

更新日期：2026-11-07。分支：feat/live-ai-integration；基于前后端分离分支09b23c0c5ec7f2fdfdbf11ead843f9033da3252a，原PR #1尚未合并，本轮PR以该分支为base，避免重复包含前一轮改动。

- DeepSeek /models和最小聊天调用返回200；项目 /api/chat 真实完成情绪识别与任务拆解，返回ready和有效当前步骤。项目集成检查禁止离线兜底，确认有两次真实模型调用。
- 密钥仅进程环境注入，未入源码或提交；没有配置持续运行的线上服务。详见 ai-integration.md。
- 更新旧模型名为deepseek-flash；新增输出上限、可选思考模式、JSON输出约束与不泄露密钥的兜底日志。
- 新增 check_llm.py：无离线兜底的真实连通检查；支持 --task 验证结构。
- 修复B06：模型返回空档、数字步骤、非法对象或截断输出不再进入任务状态机。
- 依赖补充httpx SOCKS支持，以沿用测试环境现有代理配置。
- 变更文件：backend/.env.example、app/config.py、app/llm.py、requirements.txt、check_llm.py、test_llm.py、README.md、backend/README.md、docs/ai-integration.md、deployment.md、handoff.md。
- 回归：13项Python测试、3项Node测试、独立临时数据库的离线smoke_test.py通过。
- 仍未完成：B01、B03、B04/B05、B07、对话质量调优、小程序真机及生产部署；此前浏览器视觉验收受阻状态未改变。
- 本轮实施提交：[a806399](https://github.com/MIUTLY/lightstep/commit/a8063993f5ea2b2facffe517f99aa7995defbea4)；[PR #2](https://github.com/MIUTLY/lightstep/pull/2)。前一轮提交与详细历史如下。

---

# 当前进度与交接：前后端分离

更新日期：2026-11-07。分支：feat/frontend-backend-boundary。
远端基线：6972939b1f8ea70ab312e2d7c327969b6f260009。

## 本轮目标与已完成

用户确认采用 FastAPI + SQLite 管理任务与偏好，客户端保存回执及私人留言。

- 新增 docs/architecture.md：技术方案、唯一任务状态、数据归属、五人分工及待定项。
- 新增 docs/api.md、docs/deployment.md；更新需求、根与模块 README、AGENTS.md。
- 后端新增监听地址/端口、重载、调试页开关及CORS来源配置，支持独立API部署；新增 /api/health。
- 删除完成/退出自动写手帐的路径，新数据库不创建 journal 表，旧手帐接口返回410 JOURNAL_CLIENT_ONLY。
- 旧数据库已有 journal 数据保持原样，不自动删除、不自动传给客户端。
- 网页调试页支持独立API基地址；手帐文字仅在本浏览器主动保存，不再调用 /api/journal*。
- 修复B02：HTTP便签与聊天便签都返回当前任务状态与步骤，不再错误返回idle。

变更文件：AGENTS.md、README.md、backend/.env.example、backend/README.md、backend/app/config.py、db.py、main.py、schemas.py、services.py、backend/run.py、smoke_test.py、backend/static/app.js、index.html、config.js、local-journal.js、backend/test_storage_boundary.py、test_local_journal.cjs、docs/architecture.md、api.md、deployment.md、requirements.md、handoff.md、frontend/README.md。

## 验证记录

- python -m unittest -v test_storage_boundary.py：7项通过。覆盖恢复进度、完成与退出不生成回执、便签状态、旧手帐接口不写入/不删除旧数据、跨域预检和纯API部署。
- node --test test_local_journal.cjs：3项通过。覆盖主动保存、重新读取、用户隔离、删除、坏数据保护及空间不足报错。
- smoke_test.py：mock模式、独立临时SQLite数据库，全流程通过。原自动手帐断言改为验证停用接口。
- JavaScript语法检查和 git diff --check 通过。
- 测试依赖在仓库外独立安装；Python测试使用 FastAPI 0.162.0、Pydantic 2.14.3、httpx 0.28.1。出现Starlette/httpx兼容弃用提示，当前测试仍通过。
- 自动浏览器视觉检查未完成：环境没有可运行的Chromium，官方浏览器包下载后不是有效ZIP。未宣称已完成浏览器视觉验收。
- 未验证：真实模型、uni-app/微信真机、相册保存、图片持久文件与手帐、生产部署、并发与权限。

## 下一轮与未解决项

1. B01粒度切换跳步；B03普通提问覆盖目标；B04/B05状态与参数校验；B06非法模型结构；B07结束意图仍待修复。
2. 5/10分钟预约、轻承诺到期/续时、步骤查看/重排尚未实现。
3. 小程序业务源码尚未提交。前端按 architecture.md 与 api.md 接入，停止使用旧手帐接口。
4. 退出挽留、跨天、历史、day_log保留、猫姿态和计时冲突仍待产品决定。现有里程碑话术等差异未清理，不代表产品全量验收。
5. user_id只是演示标识，正式多用户身份权限方案尚未完成。

## 相关提交

本轮实施提交：[cba23a0](https://github.com/MIUTLY/lightstep/commit/cba23a0e665fcf704e5ba96970a8c25dbdbb4efb)。以下旧记录仅为历史基线，不表示本轮仍未改代码。

---

## 历史：首次同步与原始审查


更新日期：2026-11-07（北京时间）

## 基线
本次是原始后端的首次同步；未改动业务源码。来源：lightstep-backend(1).zip。
技术栈：FastAPI、Pydantic、SQLite，附带静态网页调试页。
默认离线模式；真实模型仅审阅了调用代码和模拟异常，未用真实密钥验证。

## 已实现
- 会话打开、当前任务恢复、关键词意图分发。
- 任务三档模板拆解（写作、背词、阅读、代码、运动、收拾等）及模型调用封装。
- 开始确认、完成步骤、耗时阈值调整、主动缩小/放大、退出/休息/换任务。
- 情绪关键词识别、固定人设文案、模型失败回退。
- 便签存储及部分步骤完成后的召回；按领域累计偏好。
- 跨天任务交接、服务器手帐增删查、历史与今日小结。
- 16个API入口、网页调试界面与项目自带冒烟测试。

## 验证记录
- 原始 smoke_test.py 在独立临时SQLite数据库、LLM_PROVIDER=mock 下通过。
- FastAPI TestClient：静态首页返回200；已确认下面数项接口缺陷。
- 未测试：真实LLM效果、微信小程序联调、生产部署、并发请求。
- 未运行视觉验收；网页调试页可响应不等于小程序已实现。
- 本次续传复核：18 个业务源码/静态/运行配置与依赖文件逐字节一致，上传清单不含密钥或运行数据库。
- 本次续传环境未能重新运行冒烟测试：当前 Python 缺少 FastAPI，保留的旧测试依赖存在缓存损坏；上面的通过记录来自前次检查，不代表本次复跑。

## 已复现缺陷（尚未修复）
| 编号 | 问题与复现 | 建议验收标准 |
| --- | --- | --- |
| B01 | 背单词默认“打开单词本”，3秒完成后直接跳到“标记记不住的那几个”；两步即可结束，未背词 | 粒度调整保留必要动作的语义依赖，不跳过背词 |
| B02 | executing中 POST /api/note 返回 idle/task=null，但数据库仍executing；聊天便签分支同类 | 记录便签前后返回状态与存储状态一致，保留任务展示 |
| B03 | 执行中问“这一步要怎么做”会覆盖当前任务，标题变成该问题 | 询问执行方法不创建/覆盖目标或重置进度 |
| B04 | ready阶段即可完成步骤；duration_ms=-1被接受 | 非法状态与负数耗时拒绝，且无任何任务/计数/偏好副作用 |
| B05 | when=TYPO返回200并删除当前任务 | 非法枚举拒绝且不修改现有数据；resize等同类入参一并核查 |
| B06 | 模拟模型返回 {fine:[],normal:[42],coarse:[]} 被拆解层接受，创建任务接口500 | 无效结构/空列表/非文本步骤受控拒绝或回退，不产生500 |
| B07 | 执行中说“我累了”只返回低落回应，任务未结束 | 按确认后的结束意图规则识别；有歧义时不误删任务 |

## 尚缺或与策划有差距
- 5分钟轻承诺目前只有话术与确认状态，未实现到期/续时。
- later固定半小时，未区分5分钟和10分钟；旧提醒缺少完成/取消流程。
- 无前台无操作召回、勿扰、小程序生命周期适配。
- 无完整步骤查看/重排接口。
- 服务器手帐、计数与跨天续做和策划存在差异，详见requirements.md，待用户决定。
- 仅由传入user_id区分数据，无账号认证或身份归属验证；面向多用户部署前须另行设计。

## 推荐下一轮
先核实B01—B06并制定小范围修复方案及回归检查，不先改动有冲突的数据保留规则。
完成后在此记录实际修改文件、测试命令与结果、剩余问题和提交编号。

## 原始业务源码完整性
本次同步中，压缩包保留的业务源码/静态文件/依赖清单均逐字节不变。README 增加当前进度与交接入口。
新增 .gitignore、AGENTS.md、docs/requirements.md、docs/handoff.md。
排除真实运行数据库、Python缓存和本地占位文件。

## GitHub 同步
- 私有仓库：https://github.com/MIUTLY/lightstep
- 首次源码与文档同步提交：`chore: sync original backend and team handoff`。
- 此提交本身即首次同步版本；后续实施请记录具体提交编号。

## 完整项目目录调整
- 按用户要求，将现有后端整体迁入 backend/，业务源码和静态托管关系保持原样。
- frontend/ 预留给小程序前端成员，目前仅有接入说明，未收到业务源码。
- docs/ 放全团队需求与交接记录，根 README 和 AGENTS.md 说明模块及协作方式。
- 在 backend/ 内安装依赖、启动及测试；后续业务工作开分支并提交 PR。
- 本轮仅整理目录和文档，已知业务缺陷尚未修复；未增加任何前端业务实现。
- 提交说明：chore: organize full LightStep project workspace。
