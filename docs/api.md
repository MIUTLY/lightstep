> 最新产品规则：AI拆分用于降低行动门槛，只记录用户自报进度，不检查答案或强加理由/留证/成果验收。生成、范围澄清与计划审核同步遵守，见[行动辅助规则](action-support.md)。

> 对外文案增加统一过滤：删除明确内部括号说明，保留必要动作与任务约束；父任务动作明细改为自然换行。规则与接入见[展示文案协议](public-ai-text.md)。

> 最新修复：默认聊天由真实AI区分闲聊、任务和范围补充；任务澄清在对话页完成，focus非空才进入专注。接口字段、失败处理和前端接入见[闲聊与专注前澄清](chat-and-clarification.md)。

> 专注悬浮桌宠新增任务规则及专用接口已补充，见[focus-capture.md](focus-capture.md)。后端专用入口只新增、插入与去重；前端负责双击输入、气泡和全部侧边栏/返回/收起入口拦截，具体UI尚未实施。

> 2026-11-07最新主流程：真实AI提取多个独立任务 → 今日备忘录 → 用户选择 → 独立森林专注 → 完成/中途结束回执 → 非空当日清单全部完成的手帐事件。默认/chat协议已调整，旧单任务仅兼容。请求、幂等、事件确认和前端分工以[today-memo.md](today-memo.md)为准。

# 前端接入约定

完整请求字段与响应结构以运行中的 /docs 为准。最新计时停用、跨天保留与完成移除协议见[task-lifecycle.md](task-lifecycle.md)；前端页面需另行更新。

## 地址与身份

小程序只配置后端基地址，不配置模型供应商密钥。开发环境默认 http://127.0.0.1:8000；手机上的 127.0.0.1 指向手机自身，真机需使用可达的服务地址。部署与平台域名设置由前端成员按实际环境完成。

当前接口仍用 user_id 区分演示数据。客户端本地持久保存一个随机演示标识并随请求发送，不通过该标识承诺账号安全或跨设备身份。

浏览器 H5 前端在后端 LIGHTSTEP_CORS_ORIGINS 配置来源；CORS 只是浏览器跨域规则，不是身份认证。

## 任务调用顺序

| 操作 | 方法与路径 | 请求要点 |
| --- | --- | --- |
| 打开 | POST /api/session/open | user_id |
| 输入目标或反馈 | POST /api/chat | user_id、message |
| 现在开始 | POST /api/task/choose_time | user_id、when=now |
| 预约开始（已停用） | POST /api/task/choose_time | when=in_5_minutes/in_10_minutes/later均410 |
| 检查预约（已停用） | POST /api/reminders/poll | 恒410 TASK_TIMERS_REMOVED，无写入 |
| 普通开始确认 | POST /api/task/commit | user_id、agree=true |
| 完成当前步骤 | POST /api/step/complete | user_id、step_id（建议）；duration_ms可省略且已停用 |
| 主动拆小 | POST /api/step/resize | user_id、direction=smaller |
| 退出 | POST /api/task/exit | user_id |
| 记便签 | POST /api/note | user_id、content；与回执私人留言不同 |
| 恢复展示 | GET /api/session/state | 查询参数 user_id |
| 存活检查 | GET /api/health | 不代表真实模型供应商已连通 |

Reply 返回 reply、state、task、buttons 等字段。task 包括 title、current_step、steps_done、granularity、state、step_id，以及start_due_at（已停用，恒null）。step_id 是当前展示动作的稳定标识：同一步刷新不变，相同文字的不同动作仍有不同标识。完成时回传step_id校验当前范围；它不是请求幂等键。客户端成功后用响应替换当前展示；失败时保持原步骤，避免重复完成请求。当前还没有幂等令牌，不要自动重试写操作或允许连点完成。

只有服务端决定任务进度；客户端不要用本地数组下标自行推进。steps_done 供内部渲染或猫姿态使用，不等于允许在产品界面展示统计。

## 取消计时与跨天保留

五分钟轻承诺、任务耗时、耗时自动调档、预约和无操作召回均取消。旧提醒数据不再投递，due_reminders恒[]；AI网络超时保留。前端删除定时器和按钮，详见[生命周期及返回示例](task-lifecycle.md)。

备忘录items只返回未完成项，整项完成后移除；reorder只提交当前日期剩余项。未完成任务跨天保留；date是展示清单日期，today_date是实际日期，available_dates列出未完成清单日期。回执/手帐事实和幂等信息保留，图片和私人留言仍仅本地保存。

## 粒度调整与完成

新任务使用三层任务森林，默认中档。轻/中/重仍对应既有granularity的fine/normal/coarse；请求direction仍为smaller/bigger。加重选父节点，减轻选对应节点下第一个未完成子节点；完成集合不会因为调整改变。完成父任务只消费它剩余的叶子，然后在当前档位找下一段，第一棵完成后继续下一棵。新旧任务均不记录耗时或按耗时改档。

完整父任务的current_step包含本次叶子明细，部分完成时仅列剩余叶子，避免重做。旧三清单及_step_plan队列继续兼容，不猜测父子关系、不整体迁移；旧任务依然可打开、操作和交接。详见[任务森林协议](task-forest.md)。

TaskView保留title/current_step/state/granularity/steps_done/step_id/start_due_at，并新增：

| 字段 | 新任务 | 旧任务 |
| --- | --- | --- |
| plan_format | forest_v1 | legacy |
| node_id | 当前节点的任务内稳定ID | null |
| parent_id | 父节点ID，重档为null | null |
| remaining_leaf_ids | 本次操作覆盖的剩余叶子ID，仅当前节点范围 | [] |

steps_done仍为完成请求次数，不是叶子数量或目标完成率。step_id包含任务身份、节点及剩余范围：同一范围刷新不变，部分完成后范围改变则变化。客户端以current_step作为本次执行文案，不用完整父标题重新构造已做内容。

POST /api/step/resize和/api/step/complete新增可选step_id，值为显示时收到的TaskView.step_id。过时token返回409 STALE_TASK_STEP且无任务/计数/摩擦写入。未传token的旧客户端继续按服务端当前步骤处理；它不具备网络重试幂等保证。新森林并发提交还以SQLite事务比较完整任务快照，避免旧调整覆盖新进度。该保护不等于全部接口都有幂等/任务版本。

```json
{"user_id":"demo","direction":"bigger","step_id":"显示时的step_id"}
```

```json
{"user_id":"demo","duration_ms":30000,"step_id":"显示时的step_id"}
```

新森林执行态按钮返回“轻一点/完成这一步/重一点/今天到这吧”。/api/chat也识别“轻一点”“重一点”及既有太重/太简单别名；前端成员负责最终按钮排版，后端不修改客户端代码。ready/committing的开始流程和结束入口保留。

无法识别的已存森林版本返回409 INVALID_TASK_PLAN并保留原记录，不降级成新任务或删除。模型坏结构或语义不合格在入库前拒绝，保留旧任务，不降级到离线模板。真实AI生成、失败、重试与澄清接口见[ai-task-generation.md](ai-task-generation.md)。

## 手帐接口迁移

GET /api/journal、POST /api/journal/add、DELETE /api/journal/{entry_id} 均返回 HTTP 410，detail.code=JOURNAL_CLIENT_ONLY。前端应停止请求这些接口，不把私人留言发往后端。

回执在客户端绘制，用户选择保存时才写本地持久图片和索引；手帐读取和删除在本地执行。不要求生成前请求服务端认证或领取奖励。

backend/static/ 调试页已改为本地文本手帐示例；它只展示存储边界，不代替 uni-app 的图片生成和相册接口。

## 当前任务保护与错误约定

已存在任务时，普通提问与模糊目标表达不会覆盖任务。换任务使用明确表达，例如“换成背单词”“请换成背单词”；只说“换个任务”会先询问目标，保留原任务。问题如“这一步怎么做”“结束条件是什么”只回应当前步骤，不触发新建或退出。

### 自然收尾与疲惫反馈

- 完整表达“今天先到这吧”“结束当前任务”“我想结束了”等直接调用已有收尾逻辑，返回idle、task=null；不额外挽留，不增加完成步数，也不生成服务端回执。
- 单说“我累了”“做不动了”“想休息一下”不表示确认结束：返回原state/task，buttons为“今天到这吧”“太重了”，不写进度或摩擦地图，不请求模型。前端已有这两个标签的动作映射，可分别调用退出/拆小接口；未增加暂停状态。
- “不要结束”、条件/未来表达、引用、便签中的结束文字与结束方法提问不按退出处理。问题仍走普通回复；明确要求“能不能拆小”仍走调整接口。
- 无当前任务时，疲惫或收尾表达保持idle，不把“我想休息一下”创建成新目标。

识别采用常用完整分句规则，未知补充和复杂表达可能继续走普通对话；不能宣称覆盖所有自然语言。跨天保留及完成移除以task-lifecycle.md为准，旧日志不做破坏性迁移。此次仅验证HTTP和逻辑，微信页面显示与真机仍待联调。

| 动作 | 允许的状态 | 参数 |
| --- | --- | --- |
| 选择开始时间 | ready | now/in_5_minutes/in_10_minutes/later/not_today |
| 接受/拒绝轻承诺 | committing | agree必须为JSON布尔值 |
| 完成步骤 | executing | duration_ms必须为非负整数，不接受字符串、布尔值或小数 |
| 调整粒度 | ready/committing/executing | direction只能为smaller/bigger；调整不隐式开始任务 |

参数无效返回422，在进入业务处理前拒绝。没有当前任务或动作不符合状态时返回409，detail.code=INVALID_TASK_STATE。拒绝的请求不得修改任务、完成数量、偏好、便签或提醒，也不创建新用户。既有跨天清理沿用原规则。

user_id、聊天message和便签content去除首尾空白后不能为空；GET状态/历史/今日小结同样校验user_id。

前端当前已使用正确的枚举、布尔值与数字，错误层也已有409/422处理。收到409时保留当前展示并刷新状态；写操作不要自动重试。尚未提供请求幂等键或任务版本号，本轮未解决并发重复提交。
