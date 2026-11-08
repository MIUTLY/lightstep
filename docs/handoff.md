# 最新追加：AI拆分帮助行动，不验收用户成果

2026-11-07，继续尚未合并PR #17（fix/public-ai-text），基于其a88267d；不另开重复PR。实施[e9f6fd5a52042bc2ab986a99ef36dc9efdbf8db2](https://github.com/MIUTLY/lightstep/commit/e9f6fd5a52042bc2ab986a99ef36dc9efdbf8db2)。

用户补充的核心不是删一个“理由”词，而是降低行动门槛：解决难题可以查知识点、试写思路，用户点做完了即记录进度，不评估答案对错、完成质量或达标程度。截图里的获取确认、记录选项理由、完整性检查、最终答案交付，是AI强加的额外负担。

核对发现resolve_scope原文要求“可验证的全部完成范围”，独立审核也容易把覆盖理解为成果可验收。因此prompts.py增加共享ACTION_SUPPORT_POLICY，同时用于真实AI拆分、独立计划审核；llm.py将其用于范围澄清和范围审核，明确仅问影响拆分的对象/工作量，不索要题目全文、答案或选项验题，不替用户解题。审核检查AI计划是否忠实、省力，有额外留证/理由记录/自评/质量验收负担时用既有relevant=false拒绝，不用模板或关键词替换。

完成接口原本就仅根据用户完成操作更新当前范围叶子，不调用AI评分、不要求提交答案，因此保留此流程。若写论证、检查代码或交付报告本来就是用户明确目标/必要工作，仍保留，不能机械删除这些动作。完整性只指不漏约定的行动范围，不保证客观成果达标。

保留上轮统一展示过滤：删除内部标签，必要动作和父任务上下文、剩余范围不丢。没有盲删所有括号，也没有在输出阶段删掉“记录/理由/检查”来暗改已有森林。旧任务不自动重拆或清进度；新规则用于新生成。前端继续只展示当前一步，截图中的完整森林列表及排版由前端成员接入，本轮未代改。

修改：backend/app/prompts.py、llm.py；新增backend/test_action_support.py四项；更新AGENTS、根/后端README、api、requirements，新增[行动辅助协议](action-support.md)。本次是在同一PR补齐真实AI生成语义，而不是只做文本掩盖。

测试：
```bash
# backend目录
python -m unittest discover -s . -p 'test_*.py'
python -m unittest -v test_action_support
python smoke_test.py
```
云环境实际在根目录沿用仓库外selector辅助：
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python -m unittest -v test_action_support
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
git diff --check
```
最终164项通过（46.489s，原160+新增4）；4项专项0.214s通过；隔离冒烟、AST及diff检查通过。验证生成/审核/澄清实际收到共享行动政策，隔离审核可拒绝额外理由汇报，用户手动完成无需答案或AI评分。其余展示过滤、问答、森林进度、退出恢复、幂等和存储边界继续通过。

未验证：真实模型对数学难题、选择题、写作、家务等能否持续生成理想的短动作，及微信展示未实测。替身审核拒绝不等于真实模型一定能发现所有多余步骤。用户希望精简的旧任务需主动重新生成后才能得到新规则计划，不自动抹掉旧进度。本轮不自动合并或部署。

---

以下为此前交接。

# 最新交接：统一过滤对外AI展示文案

2026-11-07，独立分支fix/public-ai-text，基于最新main 412ebdc（#16已合并）。实施[3b1ba659887427d32bde796620f6cbc6aeefd917](https://github.com/MIUTLY/lightstep/commit/3b1ba659887427d32bde796620f6cbc6aeefd917)。本轮未合并或部署。

依据：用户要求返回前端时去掉“（本次对话：…）”等不该展示的内部说明。核对发现还有后端自己拼接的“（本次内容：动作明细）”；动作明细必须保留，不能为了去括号丢掉森林范围。

实际改动：新增backend/app/public_text.py及PublicJSONResponse统一JSON展示出口，处理reply/current_step/question/summary/feedback/title/scope和实际动作文字列表。删除完整中英文内部标签括号段与think/thinking块，支持嵌套；保留题号、字数、数量等有效括号。current_step的本次内容标签改为换行，保留全部要求完成的动作；部分完成仍明示剩余内容。backend/app/main.py配置默认响应类，使正常返回、重开及旧幂等响应均过滤，不修改存储或原始用户输入/操作命令/上下文/ID/完成集合。llm.py过滤真实闲聊正文并拒绝过滤后为空的回复；prompts.py要求只输出用户可见话语，不用固定模板兜底。

测试与文档：新增test_public_text.py 7项回归；更新test_task_forest.py的HTTP文案断言，完成范围与进度断言仍保留；test_memo.py的跨天HTTP对比区分展示投影与内部原文。同步根README、backend/README、docs/api.md、requirements、task-forest，并新增[public-ai-text.md](public-ai-text.md)。未改frontend或backend/static，不迁移用户数据库。

验证：backend目录运行：
```bash
python -m unittest discover -s . -p 'test_*.py'
python smoke_test.py
```
本云环境沿用仓库外TestClient selector辅助，实际根目录命令：
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
git diff --check
```
最终160项通过（40.223s，原153+新增7），隔离SQLite冒烟、Python AST与diff检查通过。覆盖内部标签、嵌套/中英文括号、think块、有效任务约束保留、父任务明细保留、剩余动作保留、原始输入与标识不变、已有/重放HTTP响应过滤、纯内部AI回复明确失败；既有AI失败、范围澄清、森林切换、任务完成/中断/跨天和存储边界回归仍通过。测试仅隔离模型/HTTP替身，未执行真实供应商和微信验收。

限制与前端交接：使用返回的reply/current_step等展示字段，勿把command/context/answers/original_input/plan/nodes原始数据直接渲染或从文案推算step_id。已知标签过滤不是任意内部语言的语义识别，未闭合片段及无标签普通括号不猜测删除；其他实际样例后续补规则。前端换行及微信排版、供应商真实输出仍待联调。本轮没有改变任务进度或轻重对应关系，不自动合并新PR。

---

以下为历史交接。

# 最新交接：恢复真实AI闲聊，把任务澄清放在专注前

2026-11-07。独立分支fix/chat-and-pre-focus-clarification，基于最新main b6b9d00（#15已合并为29488e7，此后主线仅修改.env.example）。实施[9ceb962eb02a75a166fbc93cf0ae7fc8008d467e](https://github.com/MIUTLY/lightstep/commit/9ceb962eb02a75a166fbc93cf0ae7fc8008d467e)。本轮不自动合并/部署。

用户复现：对话页发送“你好”得到“AI返回的任务格式不合格”；写作业范围问题被展示在专注页。原因是默认/api/chat直接提交intake，所有输入均要求非空任务清单，原有reply方法没有接入新主流程。

改动：app/llm.py新增真实AI对话分流协议，区分chat/tasks/answer并验证待答ID、类型及自然回复；app/main.py将默认/chat交给持久化chat操作；app/memo.py复用幂等、失败保存和revision保护，闲聊不创建任务、不改完成事实，任务先识别再问清范围，回答关联待澄清项。select兼容旧任务并检查整份未完成清单，存在问题时focus=null；已有scope不重复询问。森林生成本身若追问也留在专注前，不创建执行会话。专注中普通/chat返回409，桌宠新增协议保持原职责。

返回新增clarifications/can_enter_focus；前端必须以focus非空且带session_id/step作为实际跳转条件，不能先跳转再等待澄清。专注页只显示森林和手动动作，去除普通聊天/澄清输入，桌宠仍仅新增任务。详见[chat-and-clarification.md](chat-and-clarification.md)。

修改文件：backend/app/llm.py、main.py、memo.py；test_chat_routing.py新增8项，test_memo.py更新显式测试替身分流及单项澄清断言；根/后端README、api、requirements、architecture、today-memo及新增专题协议。未改frontend或backend/static。

核对主线发现.env.example被填入疑似真实密钥，本修复恢复为空，不在文档/报告中复述密钥。提交历史已包含该值，维护者需要立即在供应商后台撤销/轮换；移除示例值不能撤销旧密钥。

验证命令（backend目录）：
```bash
python -m unittest discover -s . -p 'test_*.py'
python -m unittest -v test_chat_routing
python smoke_test.py
```
本云环境沿用仓库外TestClient selector辅助，根目录实际命令：
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python -m unittest -v test_chat_routing
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
git diff --check
```
153项全部通过（39.541s，原145+新增8）；最后补强非法item_id类型校验后8项专项重新通过（0.851s），隔离SQLite冒烟、Python AST及diff检查通过。测试覆盖问候、普通闲聊不改旧任务、重复请求不重复AI、范围不清时在对话追问、回答后才可专注、明确目标不强制追问、所有任务问清、失败可重试、专注禁止普通聊天以及真实适配器协议非法类型/ID/JSON拒绝。测试均显式隔离替身，不表示真实供应商自然语言质量已验收。

未完成：前端须按新字段和focus条件在对话页提问/接收回答，专注页删除常规询问/输入，仅保留森林操作和桌宠；本轮未代改，微信页面及真实供应商质量未验收。桌宠新任务的范围可回到对话页后再澄清，不把桌宠当当前任务答疑入口。密钥轮换由供应商账户维护者完成。README和接口文档已同步，新PR待检查，不自动合并。

---

以下为历史交接。

# 最新交接：取消任务计时，跨天保留未完成任务，完成移出备忘录

2026-11-07。基于最新main `626ff302d0d5ad874f9895628cc6e17c13338957`（#14已合并），独立分支`refactor/manual-task-lifecycle`。业务与协议提交：[5cd6a1e7c5a148976d443be39bb148c577a7ef89](https://github.com/MIUTLY/lightstep/commit/5cd6a1e7c5a148976d443be39bb148c577a7ef89)。本轮不自动合并或部署。

## 修改依据与行为

用户先要求取消任务计时，随后明确预约和无操作召回也全部取消；补充未完成任务第二天保留、完成一项删一项，最后确认回执和手帐仍长期保留、重复使用。按用户既定分工只改后端和文档，前端由队友负责。

- 删除任务耗时快慢判断、耗时摩擦记录与自动调档，普通手动开始/完成/结束和主动轻重切换保留。旧duration_ms可省略，合法旧值忽略，非法类型/负数仍422。
- 删除预约创建和到期提取逻辑、五分钟承诺文案。预约选项及轮询接口返回410 TASK_TIMERS_REMOVED；start_due_at=null、due_reminders=[]。旧提醒表不破坏性删除；网络超时和业务时间戳保留。
- 旧流程不再跨天清空当前任务，零步任务也保留，旧交接不因超过七天删除。新备忘录重开优先返回专注所属日，否则当天或最近未完成清单；新增today_date/available_dates/today_all_completed，保留每项原归属日及顺序，不复制或重置森林。
- 整项完成从days[date].items移除，已完成森林不再作为待办保存；保留最少id/title/scope事实及回执/手帐事件用于防重与准确日汇总。中途退出、完成小步骤都不移除整项。排序只接受该日剩余项，已完成项不再作为悬浮桌宠插入锚点。
- 回执/手帐事件继续使用稳定ID；ack不删除本地文件。旧已完成项读取兼容转换，下一次成功写事务保存新结构，不影响未完成进度或重复生成事件。

## 修改文件

- 后端：app/services.py、db.py、granularity.py、config.py、persona.py、schemas.py、main.py、memo.py，backend/.env.example及smoke_test.py。
- 回归：test_start_reminders.py将原14项预约功能测试替换为8项停用/手动完成/跨天兼容测试；test_memo.py新增6项生命周期回归，test_focus_capture.py新增1项已完成锚点回归；更新test_ai_generation.py、test_ending_intent.py、test_step_plan.py、test_task_forest.py的旧规则断言和历史数据准备。
- 文档：AGENTS.md、根README、backend/README、requirements、api、architecture、task-forest、today-memo、focus-capture；新增[task-lifecycle.md](task-lifecycle.md)，含请求/返回示例、失败处理、迁移和前端删减清单。本交接与根CODEX_HANDOFF随后记录真实实施SHA。
- 未改任何frontend/或backend/static/文件，未提交真实.env、密钥或数据库。

## 测试命令与结果

后端目录标准命令：

```bash
python -m unittest discover -s . -p 'test_*.py'
python smoke_test.py
```

本云环境沿用仓库外TestClient selector唤醒辅助，实际在根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
git diff --check
```

最终**145项通过，38.517s**；隔离SQLite冒烟、Python AST及diff检查通过。原144项中14项旧预约测试替换为8项停用测试，再新增7项生命周期测试，共145。测试使用显式注入模型/HTTP替身与临时SQLite，不调用真实供应商、不连接用户生产数据。出现依赖的弃用提示，不影响结果。

覆盖：无耗时手动完成、耗时不会调档/记摩擦、未开始拒绝完成、旧step_id拒绝重复推进、预约410无写入、旧提醒重开/重启不投递、旧任务跨天零步及有进度保留、十题做五题结束后翌日重开及无AI续做、完成整项移除但其余不变、移除后排序、旧数据兼容、跨日查询/新增任务、昨天完成不误报今天完成、重复请求/事件确认无新增回执或手帐，以及已完成项不能作为插入锚点。既有真实AI失败、森林切换、参数、便签、专注捕获及存储边界回归仍通过。

## 剩余与前端交接

1. 按[task-lifecycle.md](task-lifecycle.md)删除前端轻承诺、预约、无操作召回、耗时上传及相关UI/缓存。网页调试页也有旧计时，未代改；当前不能宣称整款小程序已无计时。
2. items不再有已完成项，排序只交剩余ID；跨天使用date/today_date和available_dates恢复或切换旧日未完成清单。不能把items为空当作今日完成；手帐依据稳定daily_journal事件，兼容重试响应可能是旧revision，应查当前状态而非恢复旧列表。
3. 回执/手帐图片与私人留言仍仅客户端持久保存，长期访问、复用、删除和保存失败处理需要前端验收；本轮不改本地文件实现。删除任务不得删除已有回执/手帐。
4. 日期沿用Asia/Shanghai，任务保留原归属日；新增当日任务不会自动迁移旧日任务。available_dates提供所有未完成日期，前端要确保可访问。
5. 无真实AI凭据/微信运行环境，真实模型质量、页面清理、前后台/重开和本地文件长期保存未验收。旧history/day_log仅兼容，不新增完成记录页，不做历史数据破坏性删除。
6. 已关闭取消中的[PR #10](https://github.com/MIUTLY/lightstep/pull/10)，未合并计时功能且未删分支。该分支的TaskCard标签隐藏为独立前端改动，可由前端成员按需提取，不能将整份计时PR重新合入。

---

以下为历史交接；旧计时、跨天清理与完成后划线规则已被上述最新决定替代。

# 最新交接：专注桌宠新增任务的后端支持

2026-11-07，独立分支feat/focus-capture，基于main 1c26b85433e11d734d0a1707013e5d9c1249b7ae（#13已合并）。实施提交[e2ccd906774261b25db51563a9d05dcfab2d0d7c](https://github.com/MIUTLY/lightstep/commit/e2ccd906774261b25db51563a9d05dcfab2d0d7c)。本轮核对未合并分支只有#10，不带入其前端计时。按既定分工只实施后端，前端桌宠及侧边栏限制未实现，不能把本轮当成完整微信功能验收。接口与前端清单见[focus-capture.md](focus-capture.md)。新PR供审查，不沿用此前合并授权自动合并。

## 修改依据、实际改动及原因

用户要求专注页新增专用桌宠输入，只新增备忘录任务，可按用户指定位置插入；不得因“结束/换成”等词退出或替换当前任务，不影响已有进度、档位和轻承诺，成功保存后才能确认，失败可重试且不能重复。

- 新增backend/app/focus_capture.py：专用新增处理器，不调用旧意图分发。按AI结果追加、插入指定名称任务后或当前整项任务后；仅数组插入，旧项完整内容与相对顺序保留。不存在/同名目标返回简短澄清，明确选择候选ID后复用已识别任务。一个澄清链使用稳定batch_id，多个回答和重试只插入一批。
- backend/app/llm.py：增加真实AI任务和位置提取以及独立语义审核；严格校验任务列表和placement枚举，不支持重要性重排、不使用关键词模板兜底；沿用memo操作超时预算。允许AI返回简短澄清。
- backend/app/memo.py：复用原操作持久化、request_id参数校验、attempt和revision事务保护。capture_batches与清单、操作响应一起提交；已保存批次可重新确认但不重复插入。capture响应仅包含批次和反馈，无完整备忘录、森林或事件。查询视图增加navigation.sidebar_locked/can_collapse_focus，锁定由整项专注状态判断，不看小步骤完成数。
- backend/app/main.py、schemas.py：新增POST /api/focus/capture，强制当前session_id及request_id；parent_request_id关联澄清，answer和anchor_id二选一；拒绝其他action或额外字段。数据库保存异常返回安全503提示，不能先回复“收到”。
- 新增backend/test_focus_capture.py 18项；更新docs/api.md、requirements及新增focus-capture协议，记录参数、响应例子、失败/重试、并发、候选选择及前端所有入口限制。

本轮不改变五分钟轻承诺的前端状态或截止时间。后端能验证active/session_id、当前节点/档位、完成集合、旧项顺序和事件不变；真实客户端是否重置计时需前端实测。专注侧边栏限制也是前端职责，服务器的锁定标记不等于已经实现页面路由拦截。

## 测试命令与结果

backend目录：

```bash
python -m unittest discover -s . -p 'test_*.py'
python smoke_test.py
```

最终**144项全部通过**（此前126项+新增18项），39.087s；隔离SQLite冒烟通过。新增场景：默认追加多项、指定位置、当前整项后、目标缺失澄清、同名明确选择、多回答批次去重、非法候选、AI失败保留原输入重试、控制词安全、过期会话拒绝、AI期间进度变化/退出保护、重开重复确认、HTTP字段和紧凑响应、真实适配器非法位置/审核拒绝、AI澄清、单步仍锁定/整项完成或end才解锁，以及数据库提交失败回滚后重试。

当前云环境沿用仓库外TestClient selector唤醒辅助，没有提交补丁或改业务断言。实际仓库根目录命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
```

新接口通过TestClient HTTP验证；冒烟沿用旧流程兼容回归。Python AST、git diff --check通过，未修改任何frontend或backend/static文件。测试模型均为显式隔离替身，不声称真实供应商或微信实测完成。

## 待验收与交接

1. 前端需实现页面内桌宠、单击无响应/双击打开、关闭返回专注、保存成功后关闭及短气泡、失败保留输入、同批次去重。输入框不能展示完整备忘录。
2. 前端统一拦截侧边栏、备忘录/手帐/设置、“收起”、返回、tab和内部跳转，页面恢复时核对focus。单步完成不能解锁；整项完成或明确end成功才恢复入口，end失败继续锁定。
3. 前端须保留原五分钟截止时间，不因弹框、提交、失败/成功或后端revision变化重建专注。晚到响应不能恢复已退出会话。#10微信计时验收仍独立。
4. 当前无真实AI凭据，任务/位置语义识别质量与真实延迟待测；单击/双击、气泡消失、路由绕行和真实轻承诺计时未执行平台验收。
5. 插入当前专注所属日清单，跨天不自动移动任务；未定义跨日新归属规则。request_id须在首次提交前本地保存，收到同batch_id成功只弹一次气泡；后端去重不能替代客户端请求和显示管理。

---

以下为历史交接。

# 最新交接：今日多任务备忘录与独立森林专注

2026-11-07。基于main ce27b686120ee4590d393c68b47dae9389fa3d7e，独立分支feat/today-memo。本轮核对远端仅#10仍是未合并草稿，未带入其前端计时。实施提交[96c414ba21ddac4b4cb4e4083eeab4c433490c92](https://github.com/MIUTLY/lightstep/commit/96c414ba21ddac4b4cb4e4083eeab4c433490c92)。接口详见[today-memo.md](today-memo.md)。本轮新PR供审查，不沿用此前对#11/#12的合并授权。

## 依据、修改和原因

用户将主流程明确为AI识别多个独立任务、今日备忘录、选定任务、专注森林、结束回执、全天全部完成手帐。旧active_task只能存一个目标，结束会清理任务，不能承载独立进度与中途续做，因此新增外层持久化状态，复用已完成的真实AI适配器及task_forest算法。

- app/memo.py：按日保存有序清单，稳定任务ID与独立森林；单个全局专注会话记录本轮开始时完成集合。完整森林结束才标记整项完成，中途end仅结束会话；排序不开始/不切换/不重置。原始输入及操作记录持久化，可查询重试。
- app/db.py：新增memo_state、memo_operations，不迁移或删除旧任务。状态revision、请求ID与attempt在事务内校验，任务进度、回执/手帐事件和成功操作结果原子提交；AI返回时已有并发变化则409而不覆盖。旧单任务写入与备忘录专注有事务互斥保护。
- app/llm.py：真实AI提取独立任务并审核完整性/顺序/无增漏；真实AI明确范围，缺对象/数量简短追问，范围需审核，不把启动段冒充整项；随后复用森林生成和内容审核。新增ContextVar操作预算，范围/拆分/审核共享超时，避免跨请求共享可变超时状态。既有森林操作不调用AI。
- app/main.py、schemas.py：默认/chat改为清单识别，要求request_id；新增/today查询、/today/command、操作记录查询。清单写操作拒绝多余字段，complete/resize强制session_id+step_id，排序带revision。session/open与state有清单数据时返回新流程状态并保留跨天数据。
- 回执事实含整项完成/中途结束、本轮新增完成动作及所有剩余动作；手帐事件只由非空清单全部完成触发。稳定事件ID、revision、ack及客户端幂等保存协议防止重复处理。同日追加任务使原手帐事件eligible=false，再次完成更新同一事件，不生成第二个手帐身份。
- 原单任务接口保留兼容；旧/chat测试显式workflow=legacy，旧数据原样保留。已有旧active_task时选择新清单项409，需先处理旧流程，不能同时专注两项。默认/chat接口变化需要前端接入，当前页面不能直接当成新流程已完成。
- backend/test_memo.py新增21项；原测试及smoke_test显式声明legacy流程，避免测试替身成为运行模式。README、backend/README、requirements、api和新增today-memo同步主流程、接口、事件确认和前端职责。前端/静态页面、图片、随机素材、计时、回执渲染和本地手帐代码均未修改。

## 验证

在backend执行：

```bash
python -m unittest discover -s . -p 'test_*.py'
python smoke_test.py
```

最终126项通过（旧105+新增21），耗时38.634s；隔离临时SQLite冒烟通过。新增覆盖：三项识别顺序和默认提示、排序持久化、不切换当前专注、选择第二项、十题五题中途退出续做、整项完成仅划掉对应项、全部完成手帐、空日不完成、重复完成/结束/ack不增加事件、失败保留与原输入重试、澄清、AI不可用时已生成森林切换、旧token拒绝、并发进度保护、单专注、跨天保留与原请求日期、当天追加后更新同一手帐ID、旧流程互斥、默认chat和command HTTP接口、真实适配器拒绝非法识别/审核/范围。

当前云环境沿用仓库外TestClient selector唤醒辅助，未改业务断言，也未提交环境补丁。实际命令（仓库根目录）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 90s python -m unittest discover -s backend -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend timeout 30s python backend/smoke_test.py
```

Python AST和git diff --check通过。代码以隔离AI/HTTP替身验证，不调用真实供应商，不把响应样例当成真实AI效果。

## 未验证与前端交接

- 本环境仍无真实供应商配置，三项识别的实际无增漏、写作业范围追问和完整拆分质量、多个模型调用的真实时延待验收。
- 前端需接入清单/排序/选择/专注协议及request_id、revision、session_id、step_id。默认/chat返回已变化，本轮不修改队友界面。
- 回执/手帐以event.id做本地唯一键，按revision更新，落地后ack；eligible=false不能生成当天全部完成手帐。后端不能独自保证跨客户端图片保存恰好一次，客户端刷新/失败恢复须联调。私人留言不上传。
- 日期当前按Asia/Shanghai，跨天保留原日任务与进度，不自动移动到新日；其他时区/自定义日界限或手动跨日移动待产品另定。当天完成后追加任务采用更新同一手帐身份，前端需据事实更新原条目。
- #10微信五分钟验收、预约可靠送达、回执/手帐实际本地图片保存仍是独立任务；本轮不宣称完成。

---

以下为历史交接。

# 本轮合并交接：任务森林与真实AI生成进入main

日期：2026-11-07（北京时间）。用户在查看各PR状态及未验收项后明确指示“该合并的你都合并吧”，本轮据此执行#11 → #12的后端合并，不再要求额外重复确认；未新增队友review记录，也不将用户合并授权写成测试或产品验收通过。

- [PR #11](https://github.com/MIUTLY/lightstep/pull/11)已合并到main，合并提交`172432ab871ef5017587fa8a6dccbe89d57068eb`。原实施`c405a78d2b4c7b3a8b1fbc15ba58aacef836fd41`，原头`039b26fcf14e59a58dff2f15ff04d1c929a7f7dd`。
- [PR #12](https://github.com/MIUTLY/lightstep/pull/12)已从feat/task-forest改为指向main，本记录随该PR进入主线。业务实施`bbe6f60b4b9e0a44f5816e5b643b0a3d35e7de62`，本轮合并前已测试快照`07e00747c5ee3071afc39a2c67265dae6294ce15`；最终合并提交编号与状态以PR页面的merge事件为准。
- [PR #10](https://github.com/MIUTLY/lightstep/pull/10)保留草稿，未合并；五项微信平台验收仍未执行。本轮不带入轻承诺前端改动。

本轮未修改业务实现。仅合并已授权的后端工作，并更新`docs/handoff.md`、`CODEX_HANDOFF.md`和`docs/ai-task-generation.md`，消除“#11尚未合并/以feat/task-forest为目标”的过期现状说明。PR描述同步实际依赖状态。

合并前核对99个本地源码/文档文本blob与#12远端已测试快照完全一致；复用该快照的105项后端回归（37.315s，OK）、隔离冒烟及无密钥真实进程启动结果，没有把未配置环境当成真实AI成功。测试命令和场景详见下节。GitHub无自动CI和队友review记录，不将空检查列表称为CI通过。文档更新运行git diff --check；合并后核对主线树及PR状态，不对无业务变化的同一快照重复执行测试。

仍未验证：真实供应商“洗衣服/洗碗/整理桌面”的任务内容与语义复核效果、实际网络时延及微信端提示/草稿恢复。运行环境需在backend/.env配置真实AI并重启后端；git pull不会替用户部署或刷新正在运行的服务。旧任务兼容、既有跨天政策和step_id限制不在本轮重新定义。#10微信验收、预约可靠送达、回执/手帐本地保存继续独立推进。

---

## 以下为本轮合并前的实施与验证记录

# 最新交接：真实AI任务森林生成与失败保留

日期：2026-11-07（北京时间）。独立分支`fix/real-ai-task-generation`，基于尚未合并的PR [#11](https://github.com/MIUTLY/lightstep/pull/11) `feat/task-forest`头`039b26fcf14e59a58dff2f15ff04d1c929a7f7dd`。本PR先以feat/task-forest为base；#11合并后核对并改为main，不能绕过#11重复提交森林实现。不合并PR #10、不修改前端、网页静态文件、轻承诺计时、回执或手帐。

实施提交：[bbe6f60b4b9e0a44f5816e5b643b0a3d35e7de62](https://github.com/MIUTLY/lightstep/commit/bbe6f60b4b9e0a44f5816e5b643b0a3d35e7de62)。本交接作为后续文档提交记录实际代码SHA，避免自引用提交编号。完整协议见[ai-task-generation.md](ai-task-generation.md)。

## 修改、依据与原因

用户本轮明确要求：实际用户任务仅由真实AI生成，取消领域模板替代具体目标及所有静默降级；原始输入、旧任务、完成进度在失败时保留，允许重试，沿用已确认森林关系。

- `backend/app/llm.py`：移除MockLLM和所有离线回退。唯一真实兼容适配器；缺配置、连接、超时、认证、限流、服务故障、非法输出均转为安全中文错误，不输出原始供应商异常或密钥。新森林生成和独立内容复核共享逻辑预算，只在格式合法且目标相关/覆盖/父子一致/无重复全部通过时接受。支持关键歧义澄清。
- `backend/app/decompose.py`：运行模块仅保留领域偏好分类，删除所有任务/情绪模板；历史固定数据移至`backend/tests/fakes.py`，只由测试显式注入，app/run.py不导入测试包，不存在mock运行开关。
- `backend/app/config.py`、`backend/.env.example`：默认openai，保留空密钥示例。无配置服务可以启动，生成明确失败，已有森林不依赖AI。服务端改配置后须重启；旧环境LLM_PROVIDER=mock需清除/修改。
- `backend/app/prompts.py`：用具体原始目标生成完整三层嵌套结构，允许必要追问，增加独立内容审核协议。拒绝“洗衣服”变成桌面清理等与目标无关的生成结果。
- `backend/app/db.py`：只新增task_generation_drafts表，不重建旧表。保存最新草稿/原输入/澄清问答/错误和内部任务快照。有效生成在事务中同时比较草稿ID、当前任务快照，再原子替换；等待期间完成/退出等变化不可被覆盖。失败不触发提前删任务、取消预约或清理跨天任务。
- `backend/app/services.py`：删除服务层第二层模板兜底；保留原始具体目标，不以领域或剥离后的标题送模型；补识别“洗衣/洗碗”等目标；成功后才显示准备好。失败返回明确reply、原task/state、failed草稿和“重试生成”。支持重开查询、重试、澄清问答；聊天可输入“重试生成”及“补充：答案”，不偷走已有步骤控制和普通提问。
- `backend/app/main.py`、`schemas.py`：新增显式生成、草稿查询、重试和回答接口；session/state与open附带generation。生成业务失败返回200 Reply+generation.status=failed，不代表生成成功；普通AI问答异常返回502/503/504字符串detail，兼容现有错误显示。过期生成/重复成功重试409。
- `backend/check_llm.py`：--task走与运行相同的真实生成+内容复核，无兜底。`backend/smoke_test.py`自动临时SQLite并显式注入替身，不再依赖运行离线模式。
- `backend/test_ai_generation.py`新增21项；原7个测试模块迁移为显式测试替身，旧森林/队列兼容与既有业务断言继续保留，原模板成功断言改成明确失败。
- 文档：AGENTS、根/后端README、requirements、architecture、api、deployment、local-development、ai-integration、task-forest及新ai-task-generation，统一运行只支持真实AI与失败/重试约定；CODEX_HANDOFF同步入口。

## 验证命令与结果

在backend目录，正常Python环境可执行：

```bash
python -m unittest discover -s . -p 'test_*.py' -v
python smoke_test.py
```

本轮最终：**105项全部通过**（原84项+新增21项），隔离冒烟通过。测试仅用独立SQLite和显式模型/HTTP替身，不产生真实AI任务，也不证明供应商质量。

当前云沙箱存在TestClient跨线程selector唤醒限制，使用仓库外loop_factory定时唤醒辅助；未将环境补丁提交项目。实际最终命令（仓库根目录）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend LIGHTSTEP_DB=/workspace/work/real-ai-boot.db timeout 90s python -m unittest discover -s backend -p 'test_*.py' -v
```

结果：105 tests / 37.315s / OK。冒烟在backend使用同一外部运行辅助：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:. timeout 30s python smoke_test.py`，自动临时DB，通过。

另外实际以python run.py启动无密钥后端（临时DB、关闭reload、端口18741）：/api/health正常；POST /api/chat输入“洗衣服”返回generation.status=failed、AI_NOT_CONFIGURED、idle/null，无模板成功。初次沙箱禁止socket绑定；使用单条命令网络权限重跑后通过，进程随后关闭。该项不调用供应商。

Python AST解析、git diff --check通过。50个frontend/backend/static文本文件与#11基线逐blob一致；图片和其他未修改文件由远端基础树保留。

### 覆盖场景

- 洗衣、洗碗、桌面三种原始目标原样进入生成与复核，保存各自响应；这些是隔离数据，不能当成真实模型效果证明。
- 无配置/遗留mock、连接失败、超时、401/403/429/500、空/截断/坏JSON/旧清单/非法森林、非法审核或任一审核项false：明确失败，不新建任务。
- 结构正确但目标无关：语义审核reject后拒绝保存；审核超时也不保存未经审查的森林。
- 替换失败保留旧任务完整JSON、完成叶子、步数、便签、预约、day_log及用户记录；失败草稿可重开/新DB实例后重试。
- 必要澄清不创建新任务，回答携带原目标和问答继续；轻重控制不误当回答。
- 等待期间完成步骤、更新目标/草稿：过期结果不得覆盖；旧ID和成功后的再次重试被拦截。
- AI未配置时已有森林反复轻重切换、完成、查询和重开正常，完成集合不因切换改变，AI调用计数0。
- 原森林对应节点/剩余内容/下一棵树/旧格式兼容、预约、参数/状态校验、自然收尾及数据边界回归继续通过。

## 未解决与后续验收

1. 当前环境无可用真实AI配置，未调用真实供应商。需配置后分别以“洗衣服”“洗碗”“整理桌面”实测，必要澄清后检查整片森林；旧协议历史连通成功不作本轮验收。
2. 内容审核是同一真实供应商的独立请求，仍可能误判；测试证明拒绝路径，不是自然语言覆盖的形式化保证。实际时延、超时比例与语义准确度待样本验证。
3. 本轮未改任何前端。reply提供明确可显示提示，聊天已有重试/补充入口；前端成员仍需核对微信实际展示及恢复generation、专用澄清UI。后端业务失败HTTP 200必须结合generation.status判断，不能只按HTTP状态判断成功。
4. 其他接口原有跨天清理/历史规则、旧格式耗时兼容、未带step_id的网络幂等限制不在本轮改造；#10微信验收、预约可靠送达、回执/手帐本地保存独立推进。
5. 本PR依赖#11，不直接合并；队友审查后再按用户决定处理合并。

---

# 以下为历史交接

后文的默认mock/离线降级描述已由本轮真实AI规则替代，仅保留作历史记录。

# 最新交接：后端三层任务森林与对应轻重切换

日期：2026-11-07（北京时间）。按用户新规则另开feat/task-forest，基于main 7f75a7dc7c4c310050f10f23cf6378f2f20f5ebc。本轮只修改后端及文档，不合并PR #10、不带入计时/回执/手帐/前端改动。新PR提交后供审查，不直接合并。

实施提交：[c405a78d2b4c7b3a8b1fbc15ba58aacef836fd41](https://github.com/MIUTLY/lightstep/commit/c405a78d2b4c7b3a8b1fbc15ba58aacef836fd41)。数据结构、接口示例和场景映射见[task-forest.md](task-forest.md)。

## 改了什么、依据与原因

- 新增backend/app/task_forest.py：模型三层嵌套结构校验、服务端稳定ID、根/父子关系、当前节点、已完成叶子集合。中档默认，逐档找对应父/第一个未完成子，不用比例或临时重拆。父任务显示实际叶子范围，部分完成只列剩余内容。
- services.py、schemas.py、main.py：新任务生成森林；完成只消费当前显示的剩余叶子，下一段保持当前档位。新增node_id/parent_id/remaining_leaf_ids/plan_format元数据，保留原字段、接口和旧任务路径。两个写接口可带step_id，旧视图返回409；未带仍兼容但不承诺重试幂等。
- db.py：森林计划及完成计数在同一SQLite事务比较并提交，过期快照不能覆盖新完成集合；无表迁移、不删除旧任务/历史数据。
- decompose.py、prompts.py、llm.py、config.py、check_llm.py及.env.example：一次生成整棵三层关系，模型非法结构降级到合法离线森林。单独增加拆分输出预算4096，普通聊天预算不变。示例中的既有疑似密钥值已清空，未使用；历史若仍有效需更换。
- 新增backend/test_task_forest.py共26项；原test_step_plan改为明确构造旧队列，保留其12项兼容断言；存储边界测试按公开完成流程验证，模型协议和冒烟默认档位断言按新规则更新。
- 更新backend/README、docs/requirements、api、handoff、task-forest协议及CODEX_HANDOFF。所有frontend及backend/static文件逐blob核对不变。

## 验证命令与结果

backend目录可按下列清单复核，mock、独立临时SQLite：

```bash
python -m unittest -v test_task_forest.py test_step_plan.py test_llm.py test_task_flow.py test_start_reminders.py test_ending_intent.py test_storage_boundary.py
python smoke_test.py
```

- 最终实际命令在仓库根目录执行：PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend LLM_PROVIDER=mock LIGHTSTEP_DB=/workspace/work/forest-boot.db python -m unittest discover -s backend -p 'test_*.py' -v。84项后端回归通过，原始mock冒烟按新默认中档规则更新后通过。用户八个重点场景全部覆盖：往返切档、完成后加重不重做、对应轻任务起点、父任务剩余内容、多次切换进度不变、完成父后不再出现子、跨树推进、重开/数据库重启恢复。
- 另覆盖40种固定种子变形森林的随机切换/完成轨迹、模型坏结构/深度/分支/总量限制、并发相同token只能完成一批、过时快照拒绝、旧三清单/队列、跨天沿现有handoff恢复、开始前调整与预约保留。
- 当前云环境TestClient仍需仓库外sitecustomize/loop_factory唤醒适配；实际命令加PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:.、PYTHONDONTWRITEBYTECODE=1。未把环境适配加入仓库或修改断言；日志/workspace/work/forest-suite-final.log、forest-smoke.log。
- Python源码ast解析、git diff --check通过。新模型结构的真实供应商调用、语义覆盖质量及小程序联调未验证；前端由其他成员负责，没有重跑前端50项而宣称平台通过。

## 兼容与未完成项

- JSON格式独立为_task_forest/version=1；旧三清单和_step_plan/version=1不推测父子关系，继续按原路线/进度操作。数据库没有结构迁移，不能识别的已存森林409并保留。
- 新森林始终中档起步，完成后保持用户当前档位；耗时仅沉淀反馈。既有旧任务的自动调档继续兼容；这是产品新规则覆盖旧默认档位偏好的结果。
- 结构能保证每个叶子唯一归属、完成覆盖与显示范围一致；真实模型的自然语言是否完整/等价覆盖用户目标还需真实样本核验。离线未知领域只提供明确的启动段；背词离线数字范围为阿拉伯数字且本次最多100个，不声称长期目标完成。
- step_id可拒绝旧页面请求，事务可防止旧计划写回，但未携带token的客户端仍不具备重试幂等。前端成员应按接口文档接入token与最终按钮布局。
- 同日重开、数据库重启及有进度的既有跨天handoff均验证；原跨天清理与日志保留政策未改变，也未删除原journal。
- PR #10及其微信端验收由原分支/前端成员继续；本轮不混入。任何真实密钥应只放后端环境，示例中的旧值不再保留于本轮文件，但历史公开值须由用户轮换。

以下为历史记录，父子拆分新规则以本节和任务森林协议为准。

---

# PR #8 合并授权更新

2026-11-07（北京时间）：用户在知悉未完成项后明确要求合并 [PR #8](https://github.com/MIUTLY/lightstep/pull/8)，本次按此指令转为正式 PR 并合入 main；下文上一轮“保持草稿、不合并”为当时范围，已由此指令更新。没有补做或虚构队员评审、CI、微信编译和真机验收。

合并前已验证的业务代码提交为 `20b3222062cf3e2eb8fee0c9747e8a03b87406ee`，上一轮交接提交为 `030487a8bf37b6fb9caaae096b210af89a39d4ad`；本次仅追加状态记录，58项后端、28项Node与mock冒烟的结果仍来自该轮。微信编译/真机、提醒可靠送达、勿扰规则及网页持续轮询继续保留为未完成项。最终合并状态和合并提交编号见 [PR #8](https://github.com/MIUTLY/lightstep/pull/8)。

---

# 最新交接：PR #8 预约前台轮询修复与回归

日期：2026-11-07（北京时间）。用户本轮授权继续完善现有PR #8，补测试、修复已复现问题、更新原PR与交接；不合并。分支：fix/start-reminder-options。

## 远端基线与本轮提交

- 本轮开始重新核对：#4/#5/#7已合入main，重复#6已关闭；#8为open/draft，base为main。下方历史记录中的“前置未合并”已过时。
- PR #8起始head为d67bc71393ad92033ace3490166966748e6cfafc。通过GitHub连接读取固定SHA的文本源码并逐Git blob哈希核验，在隔离工作区验证；没有覆盖原上传ZIP工作区。
- 本轮实施提交：[20b3222062cf3e2eb8fee0c9747e8a03b87406ee](https://github.com/MIUTLY/lightstep/commit/20b3222062cf3e2eb8fee0c9747e8a03b87406ee)。交接文档补充提交见[PR #8提交列表](https://github.com/MIUTLY/lightstep/pull/8/commits)。本轮保持草稿，不合并、不部署。

## 修改文件、依据与结果

- `backend/app/db.py`、`schemas.py`：start_due_at仅表示待提醒预约。取出标记后返回null，停止客户端无效轮询；已标记行保留，改约仍可重新启用。依据是新增两项HTTP回归在旧代码失败；无数据库结构迁移或旧数据删除。
- `frontend/utils/startReminderPoller.js`：页面可见与存在待提醒预约分开控制；无预约、消费或取消时停表，当前页预约后重新启动；保持不重叠请求，隐藏后旧凭证无效，再显示等待旧请求结束后及时检查。
- `frontend/store/session.js`：任务响应后重新协调计时器；旧状态查询不覆盖新操作/更新查询；轮询和查询校验请求身份。旧轮询不能恢复已开始、结束或改约前的状态。
- `frontend/pages/chat/chat.vue`：递增生命周期版本，防止旧onShow完成时启动新一轮页面副作用。隐藏/卸载继续停止轮询和无操作召回。
- `frontend/api/index.js`：预约后台检查使用silent请求，断网时不反复弹toast；普通用户操作错误反馈不变。
- `backend/test_start_reminders.py`：新增消费后pending字段、状态读取、重启与改约，以及open消费后的HTTP回归。
- `frontend/tests/startReminderPoller.test.mjs`、`startReminderSession.test.mjs`、`chatReminderLifecycle.test.mjs`、`helpers/runtime.mjs`：新增22项行为回归，加载实际模块/页面script，替换平台边界并控制慢网和计时器。
- 同步`docs/api.md`、`frontend/README.md`、`CODEX_HANDOFF.md`、本文及[详细报告](change-reports/2026-11-07-start-reminder-polling.md)。保留回执/手帐业务源码，不混入迁移。

## 验证命令与结果

仓库根目录：

```bash
node --experimental-vm-modules --test --test-isolation=none frontend/tests/*.test.mjs backend/test_local_journal.cjs
git diff --check
```

backend目录，LLM_PROVIDER=mock、LIGHTSTEP_DB指向独立临时数据库：

```bash
python -m unittest -v test_start_reminders.py test_ending_intent.py test_step_plan.py test_task_flow.py test_llm.py test_storage_boundary.py
python smoke_test.py
```

- Node 28项通过：新增预约22项 + 既有步骤身份/网页本地手帐6项。新增21项首次在旧业务源码运行时有11项失败，修复后通过；之后补充了身份切换的第22项。
- Python 58项通过：原56项 + 本轮2项；新2项在旧代码均失败。全部使用临时SQLite、mock，无外部模型调用。
- 独立临时SQLite上的mock smoke通过；所改JS及chat.vue script语法、diff空白检查通过。
- 当前执行环境的TestClient跨线程selector需定期唤醒；首次完整检查中的API-only子进程未适配而超时。统一使用仓库外`sitecustomize`包装后重跑整套通过。包装只配置TestClient loop_factory，不改变路由、模型或测试断言，具体命令见详细报告。
- VM测试用模拟Vue/uni边界，不等于Vue模板/WXSS编译或微信运行时验证。本轮未做HBuilderX编译、微信工具、真机、实际5/10分钟墙钟等待、真实模型和线上验收。

## 未解决问题与下一步

1. 提醒仍为服务端取出时标记、至多返回一次；网络丢包或客户端丢弃旧响应时可能未展示。需要产品决定确认/重投协议，不能宣称可靠送达或exactly-once展示。
2. 勿扰现有规则针对无操作召回，是否屏蔽预约仍待定；本轮不选择规则。
3. 网页调试页仍未持续轮询，只在重新打开时检查；本轮主要交付uni-app生命周期回归。
4. 微信编译/真机验收待补；前端本地回执/手帐迁移另开任务；轻承诺续时、全局写幂等/版本、模型总超时预算等沿用原待办。

以下为历史交接快照，其PR状态和验证数字只代表当时；当前以本节及远端为准。

---

# 最新交接：转交Codex，预约功能以草稿保存

日期：2026-11-07（北京时间）。接手请先阅读根目录[CODEX_HANDOFF.md](../CODEX_HANDOFF.md)，其中包含全部已改内容、修改依据、PR关系、剩余任务、验证和用户要求。

[草稿PR #8](https://github.com/MIUTLY/lightstep/pull/8)；初始保存提交[76c1187](https://github.com/MIUTLY/lightstep/commit/76c118710fffa511add8113513338b700ebad552)。当前功能仍在进行中。

- 当前分支fix/start-reminder-options，基于PR #7的716057a；该PR尚未合并。
- 已写5/10分钟预约、改约/取消/重启恢复/单次取出、UTC到期时间与新接口；uni-app按钮和前台检查也已接线。依据是策划的5/10分钟选择，以及旧半小时预约重复/遗留的问题。
- 用户中途要求转交代码工作，因此本轮保存为草稿，不继续扩展功能或宣称完成微信验收。
- 56项后端测试、6项既有Node测试、JS及chat.vue script语法、独立临时数据库mock冒烟通过；新增预约前端行为测试仍缺。
- 接手重点：预约消费后停止无效轮询、慢网/隐藏/操作竞争、提醒展示确认、勿扰策略、微信编译与真机；随后完成前端本地手帐迁移等。
- 发现#6与#7同head、不同base；不要当成独立功能重复合并。当前main仅包含#1/#2/#3，#4/#5/#7及本轮均未合并。

以下为历史记录；其中“下一步”与旧缺陷状态可能已被后续轮次更新，以CODEX_HANDOFF.md及最新远端为准。

---

# 最新交接：自然收尾与疲惫反馈

日期：2026-11-07。分支fix/natural-task-ending，基于PR #5的1b0e4ecc。PR #4/#5仍未合并，本轮PR目标为fix/preserve-step-sequence；下方为历史记录，当前进度以本节为准。

实施提交：[1db31ed](https://github.com/MIUTLY/lightstep/commit/1db31ed7e4d3527d6db4ac86a013af010b045513)；[PR #7](https://github.com/MIUTLY/lightstep/pull/7)，尚未合并。

## 改了什么、依据与原因

- B07：单说“我累了”“想休息一下”时保留任务与进度，提供“今天到这吧”“太重了”两个既有动作。疲惫不代表已经选择退出，不能擅自删掉任务。
- 完整的明确收尾表达直接复用既有退出逻辑；移除“出现结束二字就退出”的规则，避免否定、条件、引用与便签误退。活跃任务不再被宽泛休息关键词清空。
- 空闲时说“我想休息一下”不创建新目标；常用疲惫/收尾不额外调用模型。未增加暂停状态，未改日志与跨天规则，未生成服务端回执。

详细依据与边界见[本轮报告](change-reports/2026-11-07-natural-ending.md)，接入行为见[api.md](api.md)。前端已有对应标签映射，业务源码本轮未修改。

## 验证与未完成

- 新增8项HTTP回归（含多状态/措辞子用例），通过全库快照检查疲惫反馈无写入、退出只清当前任务。旧services在新增回归中失败；当前44项Python测试与独立临时数据库mock冒烟通过。
- git diff --check通过，无真实模型调用；尚未做微信编译或真机联调。
- 常用完整分句规则不覆盖所有自然语言，未知复杂表达可能仍走普通对话，不应宣称语义理解全部完成。
- 仍需5/10分钟预约、轻承诺到期、前端本地回执/手帐迁移、并发幂等、微信联调；跨天/历史保留规则仍待产品统一。
- 合并顺序：PR #4 → PR #5 → 本轮PR；前置合并后把后续PR目标改为main，不直接把本轮合回前置功能分支。当前main尚未包含这些待合并修复。

---

# 最新交接：粒度切换保留动作顺序

日期：2026-11-07。分支：fix/preserve-step-sequence。基于fix/task-intent-and-validation的8bd7c4e；PR #4仍未合并，本轮以该分支为目标。下方为各轮历史记录，当前状态以本节为准。

实施提交：[6eaa388](https://github.com/MIUTLY/lightstep/commit/6eaa3889361150a79b4831e42afce22f728a9532)；[PR #5](https://github.com/MIUTLY/lightstep/pull/5)，尚未合并。

## 改了什么、依据与原因

- B01：移除不同清单间的完成比例映射，新任务以normal路线构建有序动作队列。完成只消费刚展示过的动作，防止完成“打开单词本”后跳过学习步骤。
- 粗档最多合并两个相邻动作；细档对当前动作做保守数量/并列拆分并保留剩余内容。不能确定时保留原文，不额外请求模型。原有耗时阈值和摩擦反馈保持原规则。
- TaskView增加step_id；uni-app计时与网页调试页用其识别不同动作，避免相同文字导致错误累计耗时。兼容旧后端的文字回退仍在。
- 本次小段结束不再声称整个目标完成。队列存入既有levels_json，无表结构迁移；旧任务保留当时清单、游标与已完成前缀。

详见[修改依据与边界](change-reports/2026-11-07-step-sequence.md)和[接口约定](api.md)。队友前端仅修改计时标识引用，不改变其他业务；模型配置未修改。

## 验证与待完成

- 36项Python回归、6项Node逻辑回归通过；独立临时数据库上的mock smoke_test.py通过；JS语法和git diff --check通过。
- 新增backend/app/step_plan.py、backend/test_step_plan.py、frontend/utils/stepIdentity.js及其测试。相关服务、响应、计时与文档同步更新。
- 仍需：微信编译/真机联调、B07结束意图、5/10分钟预约与轻承诺到期、前端本地回执/手帐迁移、并发幂等。当前队列顺序正确不等于初始AI拆解已完整覆盖整个目标；复杂文本拆小可能保留原文。
- 合并顺序：先PR #4，再将本轮PR的目标切换为main合并。本轮尚未合并，不应把main视为已有这些修复。

---

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
