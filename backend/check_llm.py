"""显式调用真实模型，不使用离线兜底；不会打印密钥或请求头。"""
import argparse
import json
import sys
import time

import httpx

from app.config import settings
from app.llm import OpenAICompatLLM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", action="store_true", help="额外验证一次真实任务拆解，会产生额外API调用")
    args = parser.parse_args()
    if settings.llm_provider != "openai" or not settings.llm_api_key:
        print("请在服务端配置 LLM_PROVIDER=openai 和 LLM_API_KEY；无需把密钥填入本脚本。")
        return 2
    client = OpenAICompatLLM(settings)
    started = time.monotonic()
    try:
        answer = client._chat("这是接口连通测试，只输出简短文本。", "只回复：连接成功")
        result = {"status": "remote_ok", "model": settings.llm_model,
                  "elapsed_seconds": round(time.monotonic() - started, 2),
                  "nonempty_reply": bool(answer)}
        if args.task:
            levels = client.decompose("复习操作系统的进程同步")
            result["decomposition"] = "remote_ok"
            result["tree_count"] = len(levels["trees"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except httpx.HTTPStatusError as error:
        # 不打印可能包含认证信息的响应体或异常全文。
        print(json.dumps({"status": "remote_failed", "http_status": error.response.status_code}))
    except Exception as error:
        print(json.dumps({"status": "remote_failed", "error_type": type(error).__name__}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
