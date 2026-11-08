# 前端回归

本轮新增 focusResize（真实页面处理函数 + today store，6项）与 receiptMount（首次挂载/草稿/系统信息故障，3项）。与最新主线 PR #29/#30 合并后，下方常规命令共59项通过。

另对官方 uni-app 5.36 生成的 mp-weixin 产物执行4项检查，刻意不提供全局 uni，防止源码模拟掩盖微信编译差异：

```bash
LIGHTSTEP_MP_BUILD=/absolute/path/to/dist/build/mp-weixin node --test --test-isolation=none frontend/tests/compiledFocusSmoke.cjs
```

该脚本替换微信/vendor边界，执行实际编译后的 focusFlow、systemInfo、回执与主页代码；不能代替微信平台验收。构建依赖和方式见[本轮修复报告](../../docs/change-reports/2026-11-08-homepage-resize.md)。

```bash
node --experimental-vm-modules --test --test-isolation=none frontend/tests/*.test.mjs backend/test_local_journal.cjs
```

必须使用--test-isolation=none以保证当前云环境确实逐项执行测试，而不是只报告测试文件成功。

当前流程覆盖focusFlow、focusStore、focusPageLifecycle、chatFocusReceiptLifecycle、focusReceipt：连续独立任务、返回/弹窗、网络失败、ID重试、防重、本地草稿/图片/索引和按日期追加。实际加载业务模块/SFC script，仅替换Vue/uni-app/HTTP/存储/绘图边界，不代表已编译或实测微信页面。

本轮基于main e235eedef的原25项Node回归，已有16项失败：旧chatReminderLifecycle使用过期页面与Vue mock，startReminderSession依赖已取消且主线已不存在的startReminderChecks接口。预约已由用户明确取消，因此移除这两份过期预约/旧页面测试，以当前聊天回执生命周期和focusStore网络/状态测试替代；原startReminderPoller纯兼容单元及stepIdentity测试仍保留。未恢复预约产品或修改主线旧session代码以迎合已失效接口。

后端AI适配器在主线已加入生成/审核重试，原测试仅提供一轮替身响应会StopIteration；本轮让拒绝/非法响应替身持续返回，并去掉测试中的真实退避等待，仍断言重试最终失败、不创建任务。生产重试行为未修改。
