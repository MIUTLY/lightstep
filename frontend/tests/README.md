# 前端回归

```bash
node --experimental-vm-modules --test --test-isolation=none frontend/tests/*.test.mjs backend/test_local_journal.cjs
```

必须使用--test-isolation=none以保证当前云环境确实逐项执行测试，而不是只报告测试文件成功。

当前流程覆盖focusFlow、focusStore、focusPageLifecycle、chatFocusReceiptLifecycle、focusReceipt：连续独立任务、返回/弹窗、网络失败、ID重试、防重、本地草稿/图片/索引和按日期追加。实际加载业务模块/SFC script，仅替换Vue/uni-app/HTTP/存储/绘图边界，不代表已编译或实测微信页面。

本轮基于main e235eedef的原25项Node回归，已有16项失败：旧chatReminderLifecycle使用过期页面与Vue mock，startReminderSession依赖已取消且主线已不存在的startReminderChecks接口。预约已由用户明确取消，因此移除这两份过期预约/旧页面测试，以当前聊天回执生命周期和focusStore网络/状态测试替代；原startReminderPoller纯兼容单元及stepIdentity测试仍保留。未恢复预约产品或修改主线旧session代码以迎合已失效接口。

后端AI适配器在主线已加入生成/审核重试，原测试仅提供一轮替身响应会StopIteration；本轮让拒绝/非法响应替身持续返回，并去掉测试中的真实退避等待，仍断言重试最终失败、不创建任务。生产重试行为未修改。
