# 专注页桌宠新增任务：后端与前端对接

2026-11-07，基于main 1c26b85，独立分支feat/focus-capture。后端实现专用新增入口、真实AI任务/位置识别、澄清与批次去重；不修改frontend或#10计时代码。桌宠为小程序页面内组件，不涉及系统级悬浮窗。

## 专用接口

POST /api/focus/capture，只用于新增任务。不要把这里的输入发给旧/chat、退出或换任务接口。“结束”“换成”等词不会进入后端原有意图分发，只作为新增输入交给真实AI理解；不明确时追问。

```json
{
  "user_id":"demo",
  "request_id":"capture-batch-uuid",
  "session_id":"当前focus.session_id",
  "text":"提醒我买菜，还要打电话，放在洗衣服后面"
}
```

action可省略，若传只能是focus_capture。其余额外字段拒绝，不能携带私人留言或任意任务控制字段。

AI提取新任务列表和placement(append/after_current/after_named)，独立审核任务无增漏、顺序和位置是否忠实输入；无位置要求应append，不按重要程度重排。后端只做名称匹配、目标ID解析和数组插入。after_current使用当前正在专注的整项item_id，绝不使用森林节点。多个新任务整体按表达顺序插入，其他项相对顺序、完成状态和森林原样保留。

插入范围是当前专注任务所属日的备忘录。沿用跨天不自动移动任务的规则；跨天专注仍插入该清单，不能把“当前任务后”猜成新日位置。若产品希望跨日新增归属不同，需另定。

## 成功响应

只有后端事务保存成功才返回saved=true及确认气泡。响应不包含完整备忘录、当前森林或回执事件，不应用于替换专注store。

```json
{
  "revision":12,
  "operation":{"request_id":"capture-batch-uuid","status":"succeeded"},
  "capture":{
    "saved":true,
    "batch_id":"capture-batch-uuid",
    "added_item_ids":["new-item-1","new-item-2"],
    "count":2,
    "date":"2026-11-07",
    "after_item_id":"laundry-item-id",
    "feedback":"收到，放在洗衣服后面。"
  },
  "reply":"收到，放在洗衣服后面。"
}
```

默认追加反馈“收到，放到最后啦。”；目标名称过长使用“收到，放到指定任务后面啦。”以保持气泡简短。新增项未完成、未生成森林，也不会开始专注。

## 位置澄清

目标不存在或同名项不唯一时返回operation.status=needs_clarification、capture.saved=false和question，不添加任何任务。只有同名候选返回choices(id/title/position)，不返回完整清单。

```json
{
  "revision":12,
  "operation":{"request_id":"capture-batch-uuid","status":"needs_clarification"},
  "capture":{
    "saved":false,
    "question":"有多个「洗衣服」，要放在哪一项后面？",
    "choices":[
      {"id":"laundry-1","title":"洗衣服","position":2},
      {"id":"laundry-2","title":"洗衣服","position":4}
    ],
    "context":{"batch_id":"capture-batch-uuid","original_input":"原始输入","answers":[]},
    "proposal":{"tasks":["买菜","打电话"],"placement":{"kind":"after_named","target":"洗衣服"}}
  }
}
```

context/proposal用于后端持久化澄清及重试，前端无需回传或展示。用户确认候选时：

```json
{
  "user_id":"demo",
  "request_id":"new-answer-uuid",
  "session_id":"原session_id",
  "text":"与原请求完全一致的输入",
  "parent_request_id":"capture-batch-uuid",
  "anchor_id":"laundry-2"
}
```

或用answer字符串回答“放到最后”，由真实AI结合原输入和已保存问答重新理解。anchor_id与answer二选一；anchor_id只能来自该澄清返回的候选，明确选中后复用已识别任务，不重新请求AI。多轮澄清关联上一次请求ID；整个链条使用同一batch_id，多个回答或重复点击最多提交一批任务。

## 失败、重试与并发

- AI未配置、连接失败、超时、结构/语义审核不通过：HTTP 200，operation.status=failed，error包含安全code/message/retryable，capture.saved=false，reply明确提示；不能关闭输入或显示“收到”。
- 数据库保存失败：HTTP 503，detail提示保留输入并使用原request_id重试；没有成功回执。SQLite回滚保护进度与插入结果。
- session_id过期或生成期间state.revision变化：HTTP 409，不保存旧AI结果。保留文本，核对仍是原专注后可按原参数原ID重试；专注已结束时不要自动重新开始。
- 参数错误422；同request_id更换输入/参数409。失败或网络结果不明时重用原ID及原参数，不创建新ID。用户改变输入才视为新批次。
- request_id在首次提交前生成并本地保留。后端将原输入先写入memo_operations，重开可通过已有/today/operation或/today/operations找回。网络失败若请求尚未到达服务器，只能由前端本地草稿恢复。
- request_id防止同一命令重复；capture_batches将同一澄清链的多个request_id绑定到同一已保存批次。状态、批次、操作结果在一次事务中提交；attempt和revision拒绝并发旧结果。
- 重新请求已成功批次可以再次得到相同确认，前端应按batch_id只弹一次气泡，不能因收到成功响应再追加本地任务。

## 前端实施和验收清单

1. 专注页右下角桌宠单击无响应，双击打开专用输入框。打开/关闭只是本地UI状态，不调用select、commit、complete或end；关闭回到原专注。
2. 提交处理中禁止重复发送新ID，失败保留原输入与请求ID。只有succeeded且saved=true才关闭输入并短暂展示feedback气泡；不切页、不展开备忘录。needs_clarification继续在小输入框中追问或选候选。
3. 不用捕获响应重建focus对象，不重置session_id、step_id、档位或五分钟截止时间；“收到”不算开始一个新任务。晚到响应需核对页面/会话，不能把已经退出的专注恢复出来。
4. /api/today及有备忘录数据的session/state、session/open返回navigation.sidebar_locked和can_collapse_focus；focus存在时前者true、后者false。一个森林小步骤完成仍锁定，整项森林完成或end成功才解锁；end失败继续锁定。退出不把未完成项划掉。
5. 前端统一检查侧边栏、备忘录/手帐/设置按钮、“收起”、返回、系统返回、tab切换及所有内部navigate入口，并在页面恢复时复核focus。返回若需离开专注，只能让用户明确选择end，成功后再导航。服务端标记是UI策略信号，不是接口身份权限；不能以仅隐藏侧边栏按钮代表已阻断绕路。
6. 五分钟轻承诺在弹框前后、提交失败/成功、后台恢复后保持原截止时间。预约、无操作召回和轻承诺仍分别处理，本轮未改计时。

上述页面/双击/路由/气泡/真实计时验收由前端成员执行，当前后端测试仅证明会话、森林、档位、完成集合、旧项顺序和事件未被新增修改，以及锁定标记随专注状态正确变化。真实AI识别和微信平台行为仍未实测。
