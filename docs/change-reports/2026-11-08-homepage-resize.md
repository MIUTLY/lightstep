# 主页白屏与专注轻重按钮修复

## 依据、主线和根因

用户反馈主页打不开，随后反馈专注页轻一点、重一点没有反应。本轮延续已授权的相关前后端修复，实际只修改前端及文档。

工作开始时 main 为 PR #28 合并提交 329763bdd38e4f401aa47845d6c062867410dd4b；期间队友合并 PR #29 和 #30，已同步到 cc5f8ae6304dfa797d7da1d23530a53775149115 后实施。保留队友的主页修复、步骤滚动区、按钮位置/层级、票根文字基线和字号。

- 主页：PR #28 的 `createFocusFlow({ ..., storage = uni })` 在微信编译产物中保留了裸 `uni`，调用默认存储时抛 `ReferenceError: uni is not defined`。队友 PR #29 已以延迟成员调用修复。本轮也用原版本的真实 mp-weixin 产物、无全局 uni 的执行环境复现该错误，没有重复改写 focusFlow。
- 轻重按钮：脚本把 `transitionBusy` 的 ref 对象直接用于 if，对象始终为真，所以处理函数在调用 API 前就返回。PR #30 已改善点击区域，但该判断仍在。
- 原 Node 测试给源码提供全局 uni，且未直接测试两个轻重按钮的页面处理函数；通用 Vue SFC 检查和小程序构建成功都不能证明微信运行成功。本轮补按钮到 store 链路及编译产物运行检查。

## 实际改动

- `pages/focusmode/focusmode.vue`：两个按钮共用调整处理函数，读取 `transitionBusy.value`；等待、切项、退出期间拦截。网络、业务和意外异常给出提示，无任务时保留既有提示。
- `store/today.js`：删除定位后不再需要的临时 resize 参数/结果日志，调用参数和状态更新规则不变。
- `pages/chat/chat.vue`：有待显示回执才挂载弹窗，冷启动不执行无用的回执初始化。
- `components/FocusReceiptDialog.vue`、`utils/systemInfo.js`：窗口信息读取有兼容和容错；条件挂载后首次显示立即恢复草稿并绘图。
- 测试验证正常切换、失败保留状态、并发拦截及窗口信息异常。README、需求、API与交接同步更新。

## 接口与进度

继续使用 `POST /api/today/command`，`action: resize`，轻为 `direction: smaller`，重为 `bigger`。保留 user_id、request_id、session_id、step_id。采用后端返回的 focus.step；不重新调用 AI，不根据完成比例猜位置，不增加表现计步或完成叶子。

HTTP 成功仍需检查 operation.status；failed 或网络失败时提示 lastError，保留已有状态，用户可以重试。已在最轻/最重时遵从服务端保持当前节点。

## 验证方式

仓库根目录：

```bash
node --experimental-vm-modules --test --test-isolation=none frontend/tests/*.test.mjs backend/test_local_journal.cjs
git diff --check
```

另外在仓库外建立临时 CLI 目录，复制 frontend 为 src，安装精确依赖：`@dcloudio/vite-plugin-uni`、`@dcloudio/uni-app`、`@dcloudio/uni-components`、`@dcloudio/uni-mp-weixin` 均为 `3.0.0-alpha-5030620261106001`，Vue `3.4.21`，Vite `5.2.8`。配置 Vite uni 插件后执行：

```bash
CI=1 UNI_INPUT_DIR=/workspace/work/homepage-uni-build/src npm run build:mp
# build:mp 为 uni build -p mp-weixin
```

CI=1 使用编译器自带开关关闭在线版本检查；编译本身在沙箱执行。仓库仍为 HBuilderX 非 CLI 工程，不提交依赖、构建产物或本地私有配置。构建提示未配置 uni 统计 AppID，是统计提示而非编译失败；微信 AppID配置保持原样。

常规Node回归 **59项通过**；官方 uni-app 5.36 微信目标构建成功；另对生成的产物执行 **4项通过**：

```bash
LIGHTSTEP_MP_BUILD=/workspace/work/homepage-uni-build/dist/build/mp-weixin node --test --test-isolation=none frontend/tests/compiledFocusSmoke.cjs
```

4项检查不提供全局 uni，分别验证默认存储往返、窗口API容错、回执首次挂载绘图、主页初始化与首屏无空回执组件。仍替换 vendor/平台接口，并非微信真机。实施提交见 [handoff](../handoff.md)。本轮后端生产代码与接口没有改动，未重复声称执行上轮的190项后端测试。

## 微信端仍需验收

需要拉取修复分支、重新编译，而不是继续使用旧 unpackage 产物；保留用户缓存和未完成进度。实测冷启动主页、无待办/有回执、轻中重来回切换、长步骤滚动与按钮命中、断网提示、完成/退出回到主页、草稿与预览/保存。编译产物执行验证只替换平台边界，不等于微信开发者工具或真机验收。
