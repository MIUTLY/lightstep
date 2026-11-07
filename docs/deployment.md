# 后端启动、分离部署与验证

## 开发

在 backend/ 创建并激活虚拟环境，然后安装 requirements.txt。将 .env.example 复制为 .env，默认 LLM_PROVIDER=mock，无需真实模型密钥。

```bash
cd backend
pip install -r requirements.txt
python run.py
```

默认 http://127.0.0.1:8000 为调试页，/docs 为接口文档，/api/health 为进程存活检查。

## 服务端配置

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| LIGHTSTEP_HOST | 127.0.0.1 | 监听地址；局域网联调可按实际环境设0.0.0.0 |
| LIGHTSTEP_PORT | 8000 | 服务端口 |
| LIGHTSTEP_RELOAD | true | 开发重载；部署时设false |
| LIGHTSTEP_SERVE_DEBUG_UI | true | 独立部署 API 时设false，根路径返回404，/api与/docs保持可用 |
| LIGHTSTEP_CORS_ORIGINS | http://localhost:5173,http://127.0.0.1:5173 | 逗号分隔的浏览器前端来源，上线填写实际来源 |
| LIGHTSTEP_DB | lightstep.db | SQLite 文件路径，部署时指定可写的持久目录；父目录须预先存在 |
| LLM_PROVIDER | mock | 接真实模型时设openai并填写供应商配置 |

服务端配置密钥不能放前端、仓库或客户端配置。现有 user_id 是演示标识，当前部署不代表已完成正式多用户权限方案。

SQLite 与服务在同一环境即可，不必购买独立数据库服务。备份时考虑SQLite事务和写入状态；本轮未引入自动备份或部署平台。云端实例重建后若无持久磁盘，数据库会丢失。

## 网页调试页独立托管

backend/static/ 也可由独立静态服务器托管，修改其中 config.js 的 LIGHTSTEP_API_BASE 为实际后端基地址；后端 CORS 配置该静态服务器来源。默认空字符串使用同源。

该设置只影响网页调试页。uni-app 工程接入后应维护自身环境配置，不能误把供应商地址当作业务后端地址。

## 测试

在 backend/ 执行：

```bash
python -m unittest -v test_storage_boundary.py
node --test test_local_journal.cjs
```

storage boundary 测试自动使用临时数据库。运行原有 smoke_test.py 前，通过 LIGHTSTEP_DB 指向独立临时数据库、LLM_PROVIDER=mock，不使用队员业务数据库。浏览器本地手帐在同一浏览器、同一来源下保存，不自动同步。

旧数据库中的 journal 表不会被自动删除或迁出，相关 HTTP 接口已停用。若需要清理或导出旧数据，先确认处理范围并备份，另开迁移任务。
