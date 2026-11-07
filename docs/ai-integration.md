# AI接入与验证

2026-11-07最新规则：实际运行仅真实AI，取消默认离线、领域任务模板、AI失败后模板成功路径。森林协议和错误/重试接口见[ai-task-generation.md](ai-task-generation.md)。

## 配置后端

复制backend/.env.example为backend/.env，在实际运行后端的环境填写：

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=在后端环境填写真实密钥
LLM_MODEL=deepseek-flash
LLM_THINKING=disabled
LLM_MAX_TOKENS=1024
LLM_DECOMPOSE_MAX_TOKENS=4096
LLM_TIMEOUT=30
```

openai表示兼容协议，不限定供应商。其他供应商不支持thinking参数时留空。环境变量优先于.env，修改配置后重启后端；遗留LLM_PROVIDER=mock必须清除或改openai，不能再生成离线任务。密钥不放客户端或仓库。

## 真正验证

在backend执行：

```bash
python check_llm.py
python check_llm.py --task
```

第一条发起一次真实连通聊天；--task额外发起森林生成、独立内容复核两次请求（有关键歧义时需转用应用澄清流程）。只有真实返回通过校验才输出remote_ok。配置缺失退出2，供应商/结构/内容失败退出1，成功退出0。输出不含密钥、响应体和请求头。

生成与复核共享LLM_TIMEOUT逻辑预算，各请求使用剩余时间；超时或返回过晚的结果不得写入任务。HTTP库按网络阶段执行超时，网络等待实际耗时仍需真实环境观测。服务可在无密钥时启动，/api/health只表示进程存活，已有任务操作不依赖AI。

## 本轮验证边界

隔离HTTP和服务测试验证协议、明确失败、原子替换、重试、澄清和旧进度保护，不证明模型理解目标的效果。内容复核使用同一真实供应商的独立请求，不能视为自然语言语义的形式化证明。当前环境没有可用真实供应商配置，未进行本轮真实任务样本或微信实测。配置后应分别输入“洗衣服”“洗碗”“整理桌面”，必要澄清后核对整个森林的实际内容。

## 历史连通记录

此前旧三清单协议曾用DeepSeek/deepseek-flash验证/models、最小聊天和任务创建，测试进程使用外部注入密钥。该历史结果不构成本轮森林生成、内容复核或持续可用的验收；不从历史复制密钥。
