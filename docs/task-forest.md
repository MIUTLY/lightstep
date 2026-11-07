# 后端任务森林协议与验收

2026-11-07。依据：用户本轮七项产品规则。本轮仅后端，独立分支feat/task-forest，基线main 7f75a7d；未合并PR #10或修改其他成员前端。

## AI一次生成的结构

```json
{
  "trees": [
    {
      "text": "重任务1",
      "children": [
        {"text": "中任务1", "children": [{"text": "轻任务1"}, {"text": "轻任务2"}]},
        {"text": "中任务2", "children": [{"text": "轻任务3"}, {"text": "轻任务4"}]}
      ]
    },
    {"text": "重任务2", "children": [
      {"text": "中任务3", "children": [{"text": "轻任务5"}]}
    ]}
  ]
}
```

三层含义固定，数量不固定；单子节点也允许。父/中节点必须有非空children，轻节点只能有非空text。每组最多64个，全森林最多1024个节点，text最多500字符；其他形状、独立三清单、空值、错误深度或截断输出均拒绝并离线兜底。一次建任务只请求一次拆分，后续切换/完成/重开不请求模型重拆。

关系由模型的嵌套children表达，ID与进度由服务端创建，模型不能自报完成。输出预算LLM_DECOMPOSE_MAX_TOKENS默认4096，独立于既有聊天预算LLM_MAX_TOKENS。check_llm.py --task会直接校验真实森林，不使用mock冒充远端成功；本轮未进行真实供应商验证。

## 持久化与显示范围

沿用active_task.levels_json，不改表结构，新增格式：

| 字段 | 用途 |
| --- | --- |
| _task_forest.version=1 | 与旧_step_plan队列格式区分 |
| id | 本次任务的随机唯一身份 |
| roots | 顺序排列的重任务ID |
| nodes | ID到节点的映射，含level/text/parent_id/children |
| completed_leaf_ids | 已完成最小任务的有序集合；唯一完成事实 |
| current_node_id | 当前显示节点，和active_task.level保持一致 |

节点ID在同一任务内稳定，轻/中/重内部level分别为1/2/3；granularity仍为fine/normal/coarse。父节点是否完成由它的全部叶子是否已完成推导，不另存可能矛盾的父完成标志。current_idx仅保留数据库兼容，不能用其比例反推进度。

新建选择第一个未完成中节点；摩擦偏好和输入情绪不覆盖这个默认。切轻取当前节点的第一个未完成直接子节点；切重取对应父节点；边界保持当前档。切换只改变current_node_id与档位，不改完成集合或完成计数。

current_step是本次执行范围的权威文案：

- 未部分完成的父任务：如“中任务1（本次内容：轻任务1；轻任务2）”，明示会被完成的实际动作。
- 父任务部分完成：如“这一段还剩：轻任务2”，不沿用包含已做动作的完整父文案。
- 轻任务：显示该最小动作原文。

完成只消费当前显示节点的remaining_leaf_ids。完成父任务时，它剩余叶子一并完成；同档位寻找下一个未完成节点，跨到下一棵树。新森林耗时仍反馈摩擦，但不自动改档。结束只称“这次拆出的步骤做完了”，不证明长期目标全部完成。

## HTTP接入与竞争保护

原路径不变。TaskView新增plan_format、node_id、parent_id、remaining_leaf_ids，保留现有字段。一次仍只返回当前一步，不返回完整森林供界面堆列表。steps_done是完成操作次数，不是叶子数量；父任务的一次完成仍计一次。

执行态按钮含“轻一点/完成这一步/重一点/今天到这吧”；/api/chat可识别两个新标签，原太重/太简单与smaller/bigger兼容。选时、承诺、退出、便签、提醒行为继续按原流程。前端成员负责布局和token传递，本轮未修改客户端。

完成和调整接口可选传入显示时的step_id。该标识包含任务身份、当前节点及剩余叶子范围：同一范围重开/往返切换不变，部分完成导致范围变化时改变。过时标识409 STALE_TASK_STEP，不写完成/摩擦/计数。客户端不应解析或自行构造此标识。

新森林写入还在SQLite BEGIN IMMEDIATE事务中比较原任务快照并同时提交任务和day_log计数，避免旧调整覆盖新完成集合。并发三次相同token完成只有一次200，其余409。未传token的旧客户端仍按服务端当前展示处理，不保证自动重试幂等；这不是全局任务版本/身份认证改造。

## 旧任务与范围边界

旧独立fine/normal/coarse和_step_plan队列无法推断语义对应关系，故不转换、不重置、不删除。读取不改其JSON，操作沿用原兼容队列和耗时规则。已存未知/损坏森林返回409 INVALID_TASK_PLAN，保留原记录，不把它替换为离线新任务。

同日重开、数据库重启及有进度的既有跨天handoff会保留森林/完成集合/当前范围和标识；跨天清理政策不在本轮重定义。旧journal/day_log与个人偏好不清理。

模型结构校验不等于自然语言语义证明：叶子唯一归属、执行范围、完成集合与防重做可程序验证；模型是否完整理解并覆盖用户目标需真实样本继续核对。离线预设对未知领域提供本次启动段；阿拉伯数字背词最多覆盖本次前100个，父/叶子明确区间，不宣称长期目标完成。单子节点不为凑数额外生成动作。

## 验收映射

| 用户场景 | 回归覆盖 |
| --- | --- |
| 中1→重1→逐档到轻，不丢内容 | test_medium_to_heavy_then_medium_then_light_keeps_all_content |
| 中1完成，中2→重1只剩轻3/4 | test_medium1_done_medium2_to_heavy_exposes_only_remaining |
| 中2→轻3 | test_medium2_to_light_starts_at_light3 |
| 轻1完成→中1只剩轻2 | test_light1_done_return_to_medium_only_requests_light2 |
| 多次切换/边界不改变完成记录 | test_repeated_switches_and_boundaries_do_not_change_completion_records |
| 父完成后不再出现已完成子任务 | test_completed_parent_children_never_reappear_and_next_tree_is_selected |
| 第一树完成正确进入下一树 | 同上，并验证后续逐档选到轻5 |
| 重开后关系和进度一致 | test_reopen_and_database_restart_preserve_tree_done_and_step_id；handoff roundtrip |

另有40种固定种子随机森林，反复切换并按当前范围完成，验证每个叶子恰好消费一次；父文案含糊时也必须显示完整消费明细。无效模型、旧任务、开始前调整、预约保留、过时token/快照、并发和准确结束文案均有回归。

仓库根目录本轮最终实际命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/work/pr8-runtime:/workspace/work:backend LLM_PROVIDER=mock LIGHTSTEP_DB=/workspace/work/forest-boot.db python -m unittest discover -s backend -p 'test_*.py' -v
```

84项通过。测试使用临时SQLite与模拟模型，仓库外sitecustomize/loop_factory只处理当前云环境selector唤醒；其他正常环境可直接运行unittest命令。mock冒烟在独立临时数据库通过；原有默认fine断言按用户新默认中档规则更新。旧队列12项测试改为显式构造旧格式，保留原兼容断言。

AST解析和git diff --check通过；50个前端/静态文本文件与基线blob一致，其他图片由远端基础树原样保留。未运行真实模型或小程序联调，不改动计时、回执、手帐。新实现提交：c405a78d2b4c7b3a8b1fbc15ba58aacef836fd41；供独立PR审查，本轮不合并。
