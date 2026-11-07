"""LLM 抽象层：离线 MockLLM 与 真 API（OpenAI 兼容）可插拔切换。

默认 mock：detect_emotion / decompose 走离线规则，reply 返回空（由 persona 兜底）。
接真 API：把 LLM_PROVIDER=openai 并配置 key / base_url 即可，失败时自动回退到离线规则。
"""
import json

from .config import settings
from . import decompose as offline
from .prompts import EMOTION_PROMPT, DECOMPOSE_PROMPT, PERSONA_SYSTEM, REPLY_PROMPT


class LLM:
    def detect_emotion(self, text: str) -> str:
        raise NotImplementedError

    def decompose(self, title: str) -> dict:
        raise NotImplementedError

    def reply(self, situation: str, text: str) -> str:
        raise NotImplementedError


class MockLLM(LLM):
    """离线模式：规则情绪识别 + 预设拆解，reply 交给 persona。"""

    def detect_emotion(self, text: str) -> str:
        return offline.detect_emotion(text)

    def decompose(self, title: str) -> dict:
        return offline.decompose(title)

    def reply(self, situation: str, text: str) -> str:
        return ""


class OpenAICompatLLM(LLM):
    """OpenAI 兼容 API（httpx 直接调用，避免强依赖 openai 包）。"""

    def __init__(self, s: "Settings"):
        self.base_url = s.llm_base_url.rstrip("/")
        self.api_key = s.llm_api_key
        self.model = s.llm_model
        self.temperature = s.llm_temperature
        self.timeout = s.llm_timeout

    def _chat(self, system: str, user: str) -> str:
        import httpx

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def detect_emotion(self, text: str) -> str:
        try:
            ans = self._chat(PERSONA_SYSTEM, EMOTION_PROMPT.format(text=text))
            for e in ("焦虑", "低落", "正常", "亢奋"):
                if e in ans:
                    return e
        except Exception:
            pass
        return offline.detect_emotion(text)

    def decompose(self, title: str) -> dict:
        try:
            ans = self._chat(PERSONA_SYSTEM, DECOMPOSE_PROMPT.format(title=title))
            data = json.loads(ans)
            for key in ("fine", "normal", "coarse"):
                if key not in data or not isinstance(data[key], list):
                    raise ValueError("bad decompose")
            return data
        except Exception:
            return offline.decompose(title)

    def reply(self, situation: str, text: str) -> str:
        try:
            return self._chat(PERSONA_SYSTEM, REPLY_PROMPT.format(situation=situation, text=text))
        except Exception:
            return ""


def get_llm() -> LLM:
    if settings.llm_provider == "openai":
        return OpenAICompatLLM(settings)
    return MockLLM()


llm = get_llm()
