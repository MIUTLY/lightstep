> 2026-11-08最新：每项任务独立表现计步，按当前执行号选择正常猫和固定票根；前台300秒未操作只换走神图。公共素材改由后端托管，用户文字/合成图仍仅本地；同日手帐多页追加，底图未提供。预约不恢复、轻承诺仍取消。 接口与分工见[最新素材协议](task-presentation-assets.md)。

> 最新修复：默认聊天由真实AI区分闲聊、任务和范围补充；任务澄清在对话页完成，focus非空才进入专注。接口字段、失败处理和前端接入见[闲聊与专注前澄清](chat-and-clarification.md)。

> 最新行为：整项完成即从items移除，不返回已完成列表；回执/手帐长期保留。取消全部任务计时，跨天恢复及新增字段见[task-lifecycle.md](task-lifecycle.md)。

# 今日备忘录与独立任务森林接口

本轮以main ce27b68为基础，独立分支feat/today-memo，复用真实AI和forest_v1。主流程为真实AI识别多个任务 → 今日备忘录 → 用户选择 → 专注执行 → 本轮回执 → 当天全部完成的手帐事件。前端代码未修改，需要按此协议接入。

## 任务与范围

真实AI按原话顺序提取独立任务，再独立审核是否遗漏、增加或改变约束；后端校验结构。关键词和领域分类不参与清单拆分。新建清单不会生成森林或开始专注。选择任务时，AI明确完整范围，有歧义先追问，再生成和审核完整森林；禁止把启动段当成整项完成。已生成森林直接复用。

清单项有稳定id、title、原始输入、完成状态、scope、澄清问题及问答、独立森林。列表数组顺序就是执行顺序。轻中重节点仅控制一次执行范围，completed_leaf_ids记录真实进度。只有整片森林完成才标记清单项completed=true。执行范围的语义仍需真实AI样本验收，程序无法形式化保证模型理解完整。

## 请求和响应

`POST /api/chat`现在默认进入今日任务识别，必须发送：

```json
{"user_id":"demo","request_id":"客户端生成并保留的唯一ID","message":"我今天又要写作业，又要看论文，还要洗衣服。"}
```

也可使用`POST /api/today/command`，公共字段user_id、request_id必填，action为以下之一。每次新操作新ID；同一操作的网络重试必须使用相同ID和参数，不能在重试时重新生成ID。

| action | 其他字段 | 效果 |
|---|---|---|
| intake | text | AI提取并追加当日清单，不开始专注 |
| reorder | date、revision、item_ids | item_ids必须恰好包含该日全部未完成项，仅改变顺序 |
| select | item_id；可选answer | 生成/读取对应森林并开始专注；歧义返回needs_clarification及问题，再用新ID提交answer |
| resize | session_id、step_id、direction(smaller/bigger) | 对应父子关系逐档调整，不改变完成集合 |
| complete | session_id、step_id | 完成当前展示范围；整项完成才结束会话及划掉该项 |
| end | session_id | 中途结束本轮，保留森林和进度，返回备忘录，不自动重启 |
| ack | event_id | 前端已处理并持久化该事件后确认，重复确认安全 |

GET /api/today?user_id=demo返回当天或恢复的未完成清单，可用date=YYYY-MM-DD读取保留的某日清单。GET /api/session/state、POST /api/session/open在有备忘录数据时返回相同主流程状态，不触发旧单任务跨天清理。

响应有state(memo/executing)、revision、date、items、focus、suggested_item_id、reply、all_completed、events。没有专注时reply询问第一个未完成任务；不会自动选择。focus带item_id、session_id、scope、当前step和progress。新森林从中档开始；恢复已生成森林保留上次节点和档位。

mutation另带operation.request_id/status。status为succeeded、needs_clarification或failed。AI业务失败返回HTTP 200和明确reply/error，不能只按HTTP状态认定成功；旧数据不变。参数422、过期step/session/revision或并发冲突409。重复同ID成功操作返回原响应，不再次推进进度或生成事件；缓存响应可能是旧revision，前端不得覆盖更高revision的状态，必要时GET最新状态。原ID换参数409。

GET /api/today/operation?user_id=demo&request_id=...可找回原命令和结果；GET /api/today/operations?user_id=demo列出最近50项持久化操作，供重开找回失败原始输入。失败或进程中断的请求允许同ID同参数重试；多个重试之间有attempt校验，旧尝试不能覆盖新尝试。重试跨午夜仍归原请求日期。

## 回执和手帐事实

receipt事件包含稳定id、revision、session_id、item_id、title、scope、date及outcome(completed/interrupted)。completed_actions/remaining_actions是整项实际叶子动作，session_completed_actions只含本轮新增完成动作；不能把叶子数直接称为题数。没有完成动作的中途结束也有一次回执事实。

daily_journal事件只在非空日清单全部completed时产生，包含date、item_ids、tasks及eligible=true。中途退出仍计入未完成，步数日志不参与判断。同一天使用同一手帐事件ID；当天完成后又追加任务时，该事件变为eligible=false，全部再次完成时更新同ID事实和revision，前端更新原手帐而非新增一份。

GET不会消费事件。前端必须以event.id作本地唯一键幂等保存，处理更高revision的更新，再ack。每日手帐只有eligible=true才生成；false表示原当日完成事实已过期，须取消待生成或更新原记录状态。刷新或重试可能再次收到同ID，不能再次创建图片/条目。后端提供稳定事实和确认协议，无法独自保证跨客户端图片保存事务恰好一次；该部分需要前端配合和实测。

图片素材、随机挑选、回执/手帐内容、排版、渲染、本地保存均由前端负责。接口禁止额外字段，不接收私人留言、图片或保存路径。服务端只存任务及执行事实。

## 数据、日期与兼容

新增memo_state、memo_operations两表，不改写旧active_task、handoff或旧森林。每用户备忘录状态在SQLite事务内按revision比较并更新；AI请求在事务外，返回后再校验，操作日志、任务状态和事件一起提交。单个用户同时只允许一个专注；正在专注时排序不会切换任务。选择其他任务需先显式end。

日期按Asia/Shanghai划分。跨天不自动清理未完成清单或专注；当前日无未完成任务时自动返回最近未完成清单，专注中优先返回其归属日；available_dates列出所有未完成清单日期，旧日可通过date查询继续处理。全天完成状态按清单归属日计算。其他时区、自定义日界限或跨日任务移动尚未定义，不在本轮猜测迁移。

原单任务接口保留兼容，旧数据不推测转换。旧/chat调用需显式workflow=legacy；新主流程前端必须迁移默认/chat的请求和响应。旧active_task仍存在时选择备忘录任务返回409，请先按旧流程处理旧任务；两类执行之间有事务保护。旧独立生成/轻重接口不应用来操作新备忘录的森林。

AI解析/范围/森林请求沿用同一真实适配器，整个备忘录操作共享LLM_TIMEOUT逻辑预算，超时不落地半成品。没有配置时新任务明确失败；已保存森林的查询、排序、续做、完成和结束不调用AI。
