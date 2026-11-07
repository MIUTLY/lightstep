# LightStep 项目协作约定

## 共同上下文
- 工作前阅读根目录 README.md、docs/requirements.md、docs/handoff.md、docs/architecture.md 和所改模块 README.md。
- 用户决定产品取舍；方案讨论明确需求和验收；Codex 负责代码实施、测试与交接。
- 策划冲突标为待定，不把现有行为自动当作最终需求。

## 目录与分工
- frontend/：队友已提交的uni-app微信小程序源码，构建和真机验收须单独完成。
- backend/：现有 FastAPI + SQLite；backend/static/ 是原有网页调试页，保留托管关系。
- docs/：共同需求、进度、接口和交接文档。
- 目录代表职责，GitHub 写权限并不按目录隔离。
- 每轮一个明确任务；跨目录接口变化先沟通并同步文档，避免无关重构。
- 业务修改开分支并提交 PR，由另一位队员检查后合并，不直接推送 main。

## 验证与交接
- 在 backend/ 安装 requirements.txt、运行 python run.py 和 python smoke_test.py。
- 默认 LLM_PROVIDER=mock，测试通过 LIGHTSTEP_DB 指向独立临时数据库。
- 冒烟通过仅证明覆盖的现有行为，不代表满足全部策划；业务修复补充必要回归验证。
- 模型调用考虑超时、错误和非法返回。
- 前端成员提交源码后补齐真实依赖、版本和运行命令，不凭空创建实现。
- 完成后更新 docs/handoff.md：变更、测试命令与结果、未解决问题和提交编号。
- 不提交真实 .env、密钥、数据库、缓存、虚拟环境、node_modules 和小程序本地私有配置。

## 已确认数据边界
- 任务、进度、偏好和摩擦地图由后端 SQLite 管理，前端不能重复推进。
- 回执图片和私人留言仅在客户端保存，不恢复服务端 journal 写入或自动生成。
- 原有 journal 表若存在不擅自删除；跨天、历史、退出的冲突仍需明确决定。
- 后端边界变更运行 test_storage_boundary.py；本地手帐变更运行 node --test test_local_journal.cjs。

## 每轮修改说明
- 按用户要求，每轮完成后必须说明：改了什么、依据什么需求或复现问题、为什么这样改、如何验证以及未完成项。
- 修改依据与验收结果同步写入 docs/handoff.md；需要详细说明时新增 docs/change-reports/ 下的记录。
