"""Real OpenAI-compatible provider. No offline task provider or template fallback."""
import json
from time import monotonic

import httpx

from .config import settings
from .task_forest import validate_blueprint
from .prompts import EMOTION_PROMPT, DECOMPOSE_PROMPT, REVIEW_PROMPT, PERSONA_SYSTEM, REPLY_PROMPT


class AIError(Exception):
    """Safe public failure; never include provider body, credentials or raw exception."""
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Clarification(Exception):
    def __init__(self, question):
        self.question = question


def invalid_response():
    return AIError("AI_INVALID_RESPONSE", "AI返回的任务格式不合格，尚未替换任务。请重试。")


class OpenAICompatLLM:
    def __init__(self, s):
        self.provider = s.llm_provider
        self.base_url = s.llm_base_url.rstrip("/")
        self.api_key = s.llm_api_key
        self.model = s.llm_model
        self.temperature = s.llm_temperature
        self.timeout = s.llm_timeout
        self.max_tokens = s.llm_max_tokens
        self.decompose_max_tokens = s.llm_decompose_max_tokens
        self.thinking = s.llm_thinking

    def _chat(self, system, user, *, json_mode=False, max_tokens=None, timeout=None):
        if self.provider != "openai" or not self.api_key or not self.base_url or not self.model:
            raise AIError("AI_NOT_CONFIGURED", "AI尚未正确配置，请联系维护者配置真实AI后重试。", 503)
        try:
            url = httpx.URL(self.base_url)
            if url.scheme not in ("http", "https") or not url.host:
                raise ValueError("invalid provider URL")
        except (httpx.InvalidURL, ValueError):
            raise AIError("AI_NOT_CONFIGURED", "AI服务地址配置不正确，请维护者检查后重试。", 503) from None
        payload = {
            "model": self.model, "temperature": self.temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.thinking:
            payload["thinking"] = {"type": self.thinking}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = httpx.post(f"{self.base_url}/chat/completions", json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout if timeout is None else timeout)
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") not in (None, "stop") or not isinstance(content, str) or not content.strip():
                raise ValueError("invalid model content")
            return content.strip()
        except httpx.TimeoutException:
            raise AIError("AI_TIMEOUT", "AI响应超时，尚未生成新任务。请重试。", 504) from None
        except httpx.HTTPStatusError as error:
            code = error.response.status_code
            if code in (401, 403):
                raise AIError("AI_AUTH_FAILED", "AI认证失败，请维护者检查配置后重试。", 503) from None
            if code == 429:
                raise AIError("AI_RATE_LIMITED", "AI暂时繁忙，请稍后重试。", 503) from None
            raise AIError("AI_SERVICE_FAILED", "AI服务暂时不可用，请稍后重试。", 503) from None
        except httpx.RequestError:
            raise AIError("AI_CONNECTION_FAILED", "暂时连接不上AI，请检查服务连接后重试。", 503) from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise invalid_response() from None

    def detect_emotion(self, text):
        answer = self._chat(PERSONA_SYSTEM, EMOTION_PROMPT.format(text=text))
        if answer not in ("焦虑", "低落", "正常", "亢奋"):
            raise invalid_response()
        return answer

    def decompose(self, title):
        # Generation and semantic review share one end-to-end budget.
        deadline = monotonic() + self.timeout

        def request(system, payload):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise AIError("AI_TIMEOUT", "AI响应超时，尚未生成新任务。请重试。", 504)
            raw = self._chat(system, json.dumps(payload, ensure_ascii=False), json_mode=True,
                             max_tokens=self.decompose_max_tokens, timeout=remaining)
            if monotonic() >= deadline:
                raise AIError("AI_TIMEOUT", "AI响应超时，尚未生成新任务。请重试。", 504)
            return json.loads(raw)

        try:
            data = request(DECOMPOSE_PROMPT, {"original_goal": title})
            if isinstance(data, dict) and set(data) == {"clarification"}:
                question = data["clarification"]
                if not isinstance(question, str) or not question.strip() or len(question) > 300:
                    raise ValueError("invalid clarification")
                raise Clarification(question.strip())
            forest = validate_blueprint(data)
            review = request(REVIEW_PROMPT, {"original_goal": title, "forest": forest})
            required = {"decision", "relevant", "coverage", "parent_child_consistent", "no_duplicates"}
            if not isinstance(review, dict) or set(review) != required or review["decision"] not in ("accept", "reject"):
                raise ValueError("invalid review")
            if any(type(review[k]) is not bool for k in required - {"decision"}):
                raise ValueError("invalid review checks")
            if review["decision"] != "accept" or not all(review[k] for k in required - {"decision"}):
                raise AIError("AI_CONTENT_INVALID", "AI拆分没有通过目标与父子关系检查，尚未替换任务。请重试或补充目标。")
            return forest
        except (ValueError, KeyError, TypeError, RecursionError):
            raise invalid_response() from None

    def reply(self, situation, text):
        return self._chat(PERSONA_SYSTEM, REPLY_PROMPT.format(situation=situation, text=text))


def get_llm():
    # Configuration errors are request-time failures, allowing saved tasks to work.
    return OpenAICompatLLM(settings)


llm = get_llm()
