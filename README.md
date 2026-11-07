# 轻步 LightStep

学习不用急，一步就好。帮助用户把学习目标拆成眼前一小步的 AI 伙伴，面向微信小程序开发。

## 团队入口

| 目录或文件 | 内容 | 对应工作 |
| --- | --- | --- |
| [frontend/](frontend/) | uni-app 微信小程序前端预留目录，目前尚无业务源码 | 页面、黑猫动效、感官模式、客户端计时、缓存、回执绘制 |
| [backend/](backend/) | 已有 FastAPI + SQLite 后端及网页调试页 | AI 调用、任务拆解、步骤调整、接口与数据、测试 |
| [docs/requirements.md](docs/requirements.md) | 产品主线与待定规则 | 全体成员开发前阅读 |
| [docs/handoff.md](docs/handoff.md) | 后端功能、缺陷、验证记录与下一轮任务 | 实施与验收时更新 |
| [AGENTS.md](AGENTS.md) | 团队和 Codex 协作约定 | 自动化开发前阅读 |

## 当前状态

后端原始代码已同步，已知缺陷尚未修复。真实模型效果、小程序联调与部署尚未验证。backend/static/ 是后端附带的网页调试页。小程序成员将业务源码提交至 frontend/。

退出、跨天、历史和回执规则仍有冲突，以需求文档中的待定事项为准。

## 启动后端

Python 3.10 或更高版本。从仓库根目录执行：

```bash
cd backend
python -m venv .venv
# 激活虚拟环境后执行
pip install -r requirements.txt
python run.py
```

调试页：http://127.0.0.1:8000 ，接口文档：http://127.0.0.1:8000/docs 。默认 LLM_PROVIDER=mock，无需真实密钥；配置示例为 backend/.env.example。

测试在 backend/ 内运行 python smoke_test.py，先通过 LIGHTSTEP_DB 指向独立临时数据库。更多说明见 [backend/README.md](backend/README.md)。

## 一起开发

1. 克隆整个仓库，阅读需求与交接记录。
2. 每个任务开分支，例如 feat/frontend-task-page、fix/backend-note-state。
3. 在负责目录开发；接口和共享需求变化须沟通并更新文档。
4. 提交 PR，说明修改、测试与遗留问题，由另一位队员检查后合并到 main。

前后端各自在对应目录安装依赖和运行。目录是分工约定，不是 GitHub 权限隔离。

队员接受私有仓库邀请后才能拉取和提交；入口为 Settings → Collaborators。本次尚未邀请队员。
