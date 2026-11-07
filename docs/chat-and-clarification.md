# 闲聊与专注前任务澄清

2026-11-07。修复默认/chat把“你好”等闲聊强制当成任务清单的问题。

POST /api/chat继续传user_id、message、request_id，默认workflow=today。真实AI先理解是闲聊、提出任务，还是回答已有任务范围问题：闲聊返回自然reply，不调用任务提取、不新增任务；任务输入调用原真实AI提取与语义复核；回答关联服务端已有待澄清项。不以关键词表判断闲聊，不增加离线回复兜底。

闲聊示例请求：
```json
{"user_id":"demo","request_id":"hello-1","message":"你好"}
```

响应继续是备忘录状态，reply为AI生成的自然回复，operation.status=succeeded。items、focus、事件和进度保持原业务事实；请求处理仍更新revision并记录幂等响应。重复相同request_id不再次请求AI。失败operation.status=failed，保留原始输入与已有任务，可用同ID重试；不能把HTTP200当作AI成功。

任务范围不清楚时（例如“写作业”），在对话页返回：
```json
{
  "state":"memo", "focus":null, "can_enter_focus":false,
  "reply":"是什么作业，要完成多少题？",
  "clarifications":[{"id":"任务ID","title":"写作业","question":"是什么作业，要完成多少题？"}],
  "operation":{"request_id":"add-1","status":"needs_clarification"}
}
```

用户在同一对话页通过/api/chat补充“十道数学题”，AI关联问题并复核范围；仍不充分可以继续追问。输入已经明确时不强制追问。多项任务逐项保存范围；存在待澄清项时不会提示或允许提前开始其他项。

前端流程：
1. 普通聊天始终展示reply，不把闲聊响应当成错误或任务创建。
2. 显示clarifications的问题，输入框留在对话页。can_enter_focus=false时不得跳转。
3. 调用select前仍须等服务端成功；只有focus非null且含有效session_id/step才进入专注。后端若在森林生成阶段发现新歧义，仍返回focus=null和澄清，留在对话页继续补充。can_enter_focus=true仅表示当前没有待答问题，不保证后续模型调用必然成功。
4. 专注页不放常规聊天或澄清输入，只显示当前森林步骤与手动操作；专注中普通/chat返回409。桌宠/api/focus/capture仍仅用于新增任务，不用它回答当前任务问题，不替换当前专注。
5. 已生成森林的恢复/调整/完成继续复用数据，不重复询问或生成。

旧workflow=legacy和显式intake保留兼容。旧未明确任务在select前补做范围检查，存在疑问仍不创建focus；旧select.answer暂兼容，但新版前端通过对话页/chat提交回答。真实AI未配置、失败、超时或返回协议无效时明确失败，不新增半成品执行森林。

本轮只修改后端和文档。真实供应商语义质量、多轮追问的自然程度、微信页面跳转与专注页删输入需要前端联调验收。
