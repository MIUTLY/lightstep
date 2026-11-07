# 前端接入约定

接口基线：本轮 feat/frontend-backend-boundary。完整请求字段与响应结构以运行中的 /docs 为准。

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
| 确认轻承诺 | POST /api/task/commit | user_id、agree=true |
| 完成当前步骤 | POST /api/step/complete | user_id、duration_ms |
| 主动拆小 | POST /api/step/resize | user_id、direction=smaller |
| 退出 | POST /api/task/exit | user_id |
| 记便签 | POST /api/note | user_id、content；与回执私人留言不同 |
| 恢复展示 | GET /api/session/state | 查询参数 user_id |
| 存活检查 | GET /api/health | 不代表真实模型供应商已连通 |

Reply 返回 reply、state、task、buttons 等字段。task 包括 title、current_step、steps_done、granularity、state、step_id。step_id 是当前展示动作的稳定标识：同一步刷新不变，相同文字的不同动作仍有不同标识。计时优先比较 step_id，兼容旧后端时才回退到标题和步骤文字；它不是请求幂等键。客户端成功后用响应替换当前展示；失败时保持原步骤，避免重复完成请求。当前还没有幂等令牌，不要自动重试写操作或允许连点完成。

只有服务端决定任务进度；客户端不要用本地数组下标自行推进。steps_done 供内部渲染或猫姿态使用，不等于允许在产品界面展示统计。

## 尚未补齐的接口能力

when=later 仍是旧的半小时预约，不代表5/10分钟已经实现。轻承诺到期/续时、完整步骤查看/重排尚未落地。状态与参数校验、粒度跳步已有修复分支，合并状态见 handoff.md。

## 粒度调整与完成

新任务保存 normal 清单为有序路线。粗档最多展示相邻两个动作，细档只拆当前待做动作；已完成前缀不变，剩余动作不因档位改变被丢弃。完成消费当前实际展示的动作，再按耗时辅助判断下一步大小。steps_done 仍是完成请求次数，不是原始动作数量或总目标完成百分比。

拆小支持可确认的数量和并列动作；条件、否定、序号、分数和范围等不确定文本保持原样，不调用模型猜测改写。队列耗尽仅表示这次小段结束，不证明AI或模板已经覆盖用户整个目标。SQLite表不变，队列元数据保存在既有levels_json中；旧任务首次写入时沿用当时清单和游标，不追补已经跳过的历史动作。

## 手帐接口迁移

GET /api/journal、POST /api/journal/add、DELETE /api/journal/{entry_id} 均返回 HTTP 410，detail.code=JOURNAL_CLIENT_ONLY。前端应停止请求这些接口，不把私人留言发往后端。

回执在客户端绘制，用户选择保存时才写本地持久图片和索引；手帐读取和删除在本地执行。不要求生成前请求服务端认证或领取奖励。

backend/static/ 调试页已改为本地文本手帐示例；它只展示存储边界，不代替 uni-app 的图片生成和相册接口。

## 当前任务保护与错误约定

已存在任务时，普通提问与模糊目标表达不会覆盖任务。换任务使用明确表达，例如“换成背单词”“请换成背单词”；只说“换个任务”会先询问目标，保留原任务。问题如“这一步怎么做”“结束条件是什么”只回应当前步骤，不触发新建或退出。

| 动作 | 允许的状态 | 参数 |
| --- | --- | --- |
| 选择开始时间 | ready | when只能为now/later/not_today |
| 接受/拒绝轻承诺 | committing | agree必须为JSON布尔值 |
| 完成步骤 | executing | duration_ms必须为非负整数，不接受字符串、布尔值或小数 |
| 调整粒度 | ready/committing/executing | direction只能为smaller/bigger；调整不隐式开始任务 |

参数无效返回422，在进入业务处理前拒绝。没有当前任务或动作不符合状态时返回409，detail.code=INVALID_TASK_STATE。拒绝的请求不得修改任务、完成数量、偏好、便签或提醒，也不创建新用户。既有跨天清理沿用原规则。

user_id、聊天message和便签content去除首尾空白后不能为空；GET状态/历史/今日小结同样校验user_id。

前端当前已使用正确的枚举、布尔值与数字，错误层也已有409/422处理。收到409时保留当前展示并刷新状态；写操作不要自动重试。尚未提供请求幂等键或任务版本号，本轮未解决并发重复提交。
