# PR #8：预约前台轮询行为修复

日期：2026-11-07（北京时间）。本轮由用户明确授权继续修改现有PR #8；只修复预约生命周期及已复现竞争，保持草稿，不合并。

## 复现与改动依据

| 复现 | 原因 | 本轮行为 |
| --- | --- | --- |
| 取出预约后start_due_at仍有值，前端继续发检查 | get_start_due_at没有过滤notified，poller始终持有interval | 仅暴露未取出预约；无待提醒预约时取消interval，改约后再启动 |
| hide→show时旧慢请求未完成，恢复检查只能等下个周期 | inFlight阻止立即发新请求，旧请求完成后没有补检查 | 等待旧请求完成，不并发；如果页面世代已变则立即检查当前世代 |
| 旧onShow在新onShow之后完成，还会启动页面检查和召回 | boolean可见标记不能区分不同show回调 | 用递增生命周期版本，旧回调完成后不执行页面副作用 |
| 旧syncState返回ready，覆盖已经开始后的committing | 状态查询只有递增操作版本，没有验证响应版本 | 查询比较版本、身份及busy状态，过时查询不覆盖当前状态 |
| 预约轮询断网仍弹toast | API调用使用默认非silent，poller catch拦不住请求层toast | 仅预约检查使用silent，普通操作保留错误反馈 |

不新增接口、不迁移表、不删除notified行或旧journal/day_log。start_due_at仍为可空字符串，但含义收紧为“待提醒”，后端消费后返回null；服务端仍不自动开始任务或推进步骤。提醒可靠送达和勿扰行为未确定，不修改取出即标记的协议。

## 行为验证范围

新增22项Node测试，使用实际poller、session store、API和chat.vue script，Vue/uni与HTTP边界使用受控替身；计时器和Promise可控制，不依赖真实等待。

- 即时检查、重复start、慢网跨多个周期且不重叠、隐藏/卸载、恢复后及时检查。
- 无预约不建计时器、消费后停止、同页改约重启，不自动开始/完成任务。
- 开始、今天不做、退出、换任务、改约、尚未完成的操作、隐藏及身份切换时旧轮询不能更新视图。
- 状态恢复请求乱序、开始后的旧ready查询、重复onShow和卸载等待回调。
- 5/10分钟枚举映射、网络失败后可检查、预约检查不弹toast或系统气泡。

旧源码首次运行新增21项时11项失败，证明停表/恢复竞争等问题；其余原有保护路径已通过，不重复声称本轮首次修复。之后补充身份边界的第22项。新增2项后端回归在旧代码均失败，修复后58项后端测试通过。

## 本环境的有效验证命令

本环境：Node v24.22.1、Python 3.12.14、FastAPI 0.141.1、Starlette 1.6.0、Pydantic 2.13.4、httpx 0.28.1。

Node（根目录）：

```bash
node --experimental-vm-modules --test --test-isolation=none frontend/tests/*.test.mjs backend/test_local_journal.cjs
```

结果：28项通过，0失败。使用VM Modules加载实际ES模块和别名；这是Node实验能力，会打印提示。`--test-isolation=none`用于当前沙箱的子进程限制，不改变断言。测试不是微信编译器。

Python（backend目录）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:. LLM_PROVIDER=mock LIGHTSTEP_DB=/workspace/work/pr8-boot.db timeout 60s python -m unittest -v test_start_reminders.py test_ending_intent.py test_step_plan.py test_task_flow.py test_llm.py test_storage_boundary.py
```

结果：58项通过。模块测试自行创建临时SQLite并清理。测试运行时的`/workspace/work/pr8-runtime/sitecustomize.py`只导入仓库外`testclient_runtime`，后者为TestClient的loop_factory增加10ms selector唤醒；子进程继承该配置。首次主进程单独适配时，既有API-only子进程因没有适配超时，统一配置后整套重跑通过。未把环境补丁加入项目或依赖。

冒烟用仓库外包装，在`tempfile.TemporaryDirectory`内设置LLM_PROVIDER=mock与LIGHTSTEP_DB，通过subprocess执行原始smoke_test.py；继承同一运行时包装，退出0。有效原始脚本未改。本环境日志位于`/workspace/work/pr8-suite-with-runtime.log`、`pr8-node-final.log`、`pr8-smoke.log`。

所改JS的`node --check`、chat.vue提取script的`node --input-type=module --check`及`git diff --check`均通过；语法检查不证明Vue模板或微信构建正确。

## 保留限制

- 取出即标记仍可能丢失展示；停止无效轮询不等于可靠送达，未新增确认/重投协议。
- 勿扰只按现有无操作召回执行，预约与勿扰关系仍待产品决定。
- 网页调试页没有持续检查。本轮保留其既有行为，防止扩大任务。
- 尚未运行HBuilderX/微信编译、WXSS、真机和真实5/10分钟等待，也未使用真实模型或部署服务器。
- 本轮operationVersion是本地旧响应保护，不是服务端任务版本或幂等键，不能宣称全局写操作并发安全。

本轮实施提交：20b3222062cf3e2eb8fee0c9747e8a03b87406ee。PR仍为草稿，另由队员审查并在完成产品/微信验收后决定合并。
