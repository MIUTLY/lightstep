# AI 接入与真实调用验证

验证日期：2026-11-07。供应商：DeepSeek；模型：deepseek-flash。

## 已验证结果

- 供应商 /models 返回HTTP 200，模型列表包含 deepseek-flash 与 deepseek-v4-pro。
- 一次最小聊天请求返回HTTP 200和“连接成功”；该请求供应商报告共11个token。
- 项目 /api/chat 用“我想复习操作系统的进程同步”建立任务，返回HTTP 200、state=ready及模型生成的当前步骤。
- 该项目集成检查调用真实模型两次（情绪识别和任务拆解），测试中禁止离线兜底，因此不是模板伪装成连接成功。
- 真实生成步骤之一：“把进程同步那章的标题和小标题抄一遍，抄完就算完成。”此处只证明链路与结构可用，不代表步骤质量已经充分验收。
- 密钥仅由本次测试进程的环境注入，未写入项目配置、代码、文档或提交；测试结束后没有部署一个持续运行的线上服务。

## 服务端配置

在实际运行后端的电脑或部署环境中，复制 backend/.env.example 为 backend/.env，然后配置：

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=在运行后端的环境填写
LLM_MODEL=deepseek-flash
LLM_THINKING=disabled
LLM_MAX_TOKENS=1024
LLM_TIMEOUT=60
```

openai 在这里是兼容协议名称，不是要求购买某一供应商服务。示例使用非思考模式和单次输出上限；超出输出上限导致内容截断时，应用会受控回退。其他供应商不支持 thinking 参数时把 LLM_THINKING 留空。

仓库默认仍为mock，保证团队无密钥可调试。环境变量优先于.env，若终端已设置 LLM_PROVIDER=mock，修改.env不会覆盖它。改配置后重启后端。

模型密钥只配置在后端，不放在小程序、调试页config.js或GitHub。SQLite和回执本地存储的分工不变。

## 如何确认真正接通

在 backend/ 内执行：

```bash
python check_llm.py
python check_llm.py --task
```

第一个命令发起一次真实聊天请求；--task额外发起一次真实任务拆解，会产生额外API调用。只有真实返回且校验通过才输出 remote_ok，不使用离线兜底。配置缺失退出码2；远端失败或结构错误退出码1；全部成功退出码0。脚本不打印密钥、请求头、供应商响应体或用户隐私。

应用正常运行时依然保留离线兜底；控制台会按阶段记录简短fallback日志，只含异常类型。因此“网页能回复”或 /api/health 正常不等于模型已经接通。

## 本轮代码调整

- 默认DeepSeek模型名由旧的deepseek-chat改为已实测的deepseek-flash。
- 增加 LLM_MAX_TOKENS、可选 LLM_THINKING；拆解请求要求JSON对象。
- 校验三档步骤均为非空文本列表；空结果、数字步骤、非法结构与截断输出受控回退，修复原B06非法模型结果导致500的问题。
- 模型调用异常仅记录类型，避免打印密钥或供应商原始错误内容。
- httpx增加SOCKS支持，解决本次环境已有SOCKS代理但缺socksio依赖的问题；沿用环境代理与TLS校验。

## 验证与剩余工作

- python -m unittest -v test_llm.py test_storage_boundary.py：13项通过。
- node --test test_local_journal.cjs：3项通过。
- mock模式、独立临时数据库的smoke_test.py通过。
- 真实调用已验证连接、结构和任务创建；尚未覆盖所有情绪表达、长期对话质量、模型超时统计、小程序真机和生产部署。
- B01粒度跳步、B03普通提问覆盖任务、B04/B05参数与状态校验、B07结束意图仍在待办。

官方协议参考：https://api-docs.deepseek.com/ 、https://api-docs.deepseek.com/guides/thinking_mode/ 。
