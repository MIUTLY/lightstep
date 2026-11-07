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

Reply 返回 reply、state、task、buttons 等字段。task 包括 title、current_step、steps_done、granularity、state。客户端成功后用响应替换当前展示；失败时保持原步骤，避免重复完成请求。当前还没有幂等令牌，不要自动重试写操作或允许连点完成。

只有服务端决定任务进度；客户端不要用本地数组下标自行推进。steps_done 供内部渲染或猫姿态使用，不等于允许在产品界面展示统计。

## 尚未补齐的接口能力

when=later 仍是旧的半小时预约，不代表5/10分钟已经实现。轻承诺到期/续时、完整步骤查看/重排尚未落地。状态校验和粒度跳步等已知问题见 handoff.md。

## 手帐接口迁移

GET /api/journal、POST /api/journal/add、DELETE /api/journal/{entry_id} 均返回 HTTP 410，detail.code=JOURNAL_CLIENT_ONLY。前端应停止请求这些接口，不把私人留言发往后端。

回执在客户端绘制，用户选择保存时才写本地持久图片和索引；手帐读取和删除在本地执行。不要求生成前请求服务端认证或领取奖励。

backend/static/ 调试页已改为本地文本手帐示例；它只展示存储边界，不代替 uni-app 的图片生成和相册接口。
