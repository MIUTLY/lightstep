# 手动任务流程、跨天保留与完成移除

2026-11-07，取代早期计时、预约、无操作召回与完成后划线的规则。

## 产品决定与后端实现

- 取消五分钟轻承诺、任务耗时、按耗时调档、预约开始和无操作召回。保留网络请求超时与数据库时间戳，它们不推进任务。
- 只有用户明确完成当前步骤才消费对应剩余叶子。主动轻重切换、手动开始/结束、森林复用与AI失败保护继续有效。
- 未完成整项任务跨天保留，节点、档位、已完成叶子、顺序不重置；跨天打开不会自动新建专注、完成步骤或生成回执。
- 整项约定范围全部完成后从备忘录移除，不返回已完成列表。完成森林小步骤不移除整项。中途结束保留未完成项。
- 回执与手帐长期保留、可反复查看使用。图片、私人留言及本地文件仍由前端持久保存；后端不上传这些内容，也不新增完成历史页面。
- 后端仅保留回执/手帐事实及幂等信息。完成项从`days[date].items`移除，其森林不再作为可执行任务保存；`finished`只保存id/title/scope用于判断当日全部完成及更新手帐事实，不向备忘录返回。
- 旧版已完成项读取时转换为上述事实，下一次成功写事务持久化；未完成森林及事件保持不变。重复完成使用同一request_id返回原操作结果，不再删下一项或再生成事件。

## 前端接口变动

主流程继续使用[today-memo.md](today-memo.md)。例如手动完成：

```json
{"user_id":"demo","request_id":"complete-unique-1","action":"complete","session_id":"服务端会话ID","step_id":"当前步骤ID"}
```

POST `/api/today/command`成功后`items`只含未完成任务；整项完成后对应项消失，`focus=null`，回执事件保留。失败保留页面/任务，不本地先删除。`reorder.item_ids`现在必须恰好包含所选日期所有未完成项，不再含已完成ID；失败409刷新版本，422修正参数。

GET `/api/today?user_id=demo`、GET `/api/session/state`、POST `/api/session/open`：

- `date`是当前返回清单的归属日，`today_date`是实际日期（Asia/Shanghai）。有专注优先返回该专注所属日；否则当天有未完成任务时返回当天，若当天没有则返回最近仍有未完成项的日期。
- `available_dates`为所有仍有未完成项的日期，倒序排列。前端需让旧日未完成清单可达，不能仅按设备当天日期过滤。指定`date=YYYY-MM-DD`可读取任一保留日，跨日不复制/自动迁移任务。
- `all_completed`仅表示返回日期的清单曾有任务且已全部完成；`today_all_completed`明确表示实际今天。无任务且从未完成过任务的空日为false。手帐仍以稳定的`daily_journal`事件为准，不能以`items=[]`推断完成。
- 已完成日不出现在待办日期索引中；按日期查询也不返回已完成任务。回执/手帐由本地已保存内容提供长期访问，ack只停止事件重投，不删除本地文件。

跨天示例（11月7日未完成，11月8日登录）：

```json
{
  "state":"memo", "date":"2026-11-07", "today_date":"2026-11-08",
  "available_dates":["2026-11-07"],
  "items":[{"id":"作业ID","title":"写作业","completed":false,"progress":{"generated":true,"completed_leaf_ids":["题1","题2"],"remaining_leaf_ids":["题3"]}}],
  "focus":null, "all_completed":false, "today_all_completed":false
}
```

示例省略其他既有字段。新日新增任务仍属于新日；旧日原顺序及进度可通过available_dates/date查询继续处理。原归属日全部完成事件仍属于原日，不把昨天完成的事实算作今天清空待办。

## 旧接口兼容

- POST `/api/step/complete`只需user_id，建议携带step_id防止过时完成。旧duration_ms变为可选弃用字段，合法值忽略、不保存、不影响档位或摩擦；负数/布尔/字符串/小数仍422。
- POST `/api/task/choose_time`只支持now/not_today；in_5_minutes/in_10_minutes/later返回410 `TASK_TIMERS_REMOVED`，拒绝前不读写业务数据。
- POST `/api/task/commit`保留普通开始确认以兼容旧状态，不承诺五分钟，也没有到期动作。
- POST `/api/reminders/poll`恒410 `TASK_TIMERS_REMOVED`；请停止调用。`start_due_at`恒null，`due_reminders`恒[]。旧提醒表不破坏性迁移，但不会投递或新建提醒。
- 旧单任务跨天不再清理或过期丢弃交接，既有完成日志不做破坏性迁移；最新备忘录不返回完成记录。旧history只为旧客户端兼容，前端不再使用它建设完成记录页。

失败响应示例：

```json
{"detail":{"code":"TASK_TIMERS_REMOVED","message":"预约提醒已取消，请停止轮询；任务由你手动开始。"}}
```

## 前端成员删减清单（本轮未修改）

1. 删除轻承诺倒计时、到期继续/结束询问、后台累计/截止时间缓存；停止useFiveMinuteAnchor及相关focus/chat生命周期挂载（含尚未合并的#10）。
2. 删除useSoftRecall、无操作召回的定时器和提示；保留用户主动发呆/记录便签等入口。
3. 删除5/10分钟预约按钮、startReminderPoller与轮询生命周期；410不可当作待重试的网络故障。
4. 删除store/session、API封装和网页调试页的步骤耗时测量/上传；网络超时、气泡短暂显示、动画计时保留。
5. 主流程直接用服务端items展示未完成项，完成成功后移除；错误不删。排序只提交剩余项，跨天恢复服务端date和available_dates。
6. 回执/手帐图片转本地持久文件，索引与私人留言留在客户端；删除待办不得连带删除回执/手帐。使用稳定事件ID保存并确认，重开能反复查看，不重复生成。

本轮自动化只验证后端，不能据此宣称微信端计时组件已删除或本地手帐长期保存已验收。
