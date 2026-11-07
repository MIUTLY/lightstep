"""轻步 LightStep 后端配置。

所有配置项都可通过环境变量或项目根目录下的 .env 文件覆盖。
离线模式（LLM_PROVIDER=mock）不需要任何外部依赖和 key。
"""
import os
from dataclasses import dataclass

# 项目根目录（app/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path: str) -> None:
    """极简 .env 加载，避免额外依赖 python-dotenv。"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _resolve_db_path(raw: str) -> str:
    """相对路径一律解析到项目根目录，避免受启动时 cwd 影响。"""
    if not raw or os.path.isabs(raw):
        return raw or "lightstep.db"
    return os.path.join(BASE_DIR, raw)


@dataclass
class Settings:
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    server_reload: bool = True
    serve_debug_ui: bool = True
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    # LLM 提供方：mock（离线）| openai（OpenAI 兼容 API）
    llm_provider: str = "mock"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-flash"
    llm_temperature: float = 0.7
    llm_timeout: float = 30.0
    llm_max_tokens: int = 1024
    llm_decompose_max_tokens: int = 4096
    # 留空时不发送供应商扩展参数；DeepSeek 可配置 disabled / enabled。
    llm_thinking: str = ""
    # 数据
    db_path: str = "lightstep.db"
    # 自适应粒度阈值（秒）
    fast_threshold: float = 15.0
    slow_threshold: float = 90.0

    def __post_init__(self):
        if self.llm_thinking not in ("", "enabled", "disabled"):
            raise ValueError("LLM_THINKING must be empty, enabled or disabled")
        if self.llm_decompose_max_tokens <= 0:
            raise ValueError("LLM_DECOMPOSE_MAX_TOKENS must be positive")
        if self.llm_max_tokens <= 0:
            raise ValueError("LLM_MAX_TOKENS must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            server_host=os.getenv("LIGHTSTEP_HOST", "127.0.0.1").strip(),
            server_port=int(os.getenv("LIGHTSTEP_PORT", "8000")),
            server_reload=os.getenv("LIGHTSTEP_RELOAD", "true").lower() in ("1", "true", "yes"),
            serve_debug_ui=os.getenv("LIGHTSTEP_SERVE_DEBUG_UI", "true").lower() in ("1", "true", "yes"),
            cors_origins=tuple(origin.strip() for origin in os.getenv(
                "LIGHTSTEP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",") if origin.strip()),
            llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", "deepseek-flash").strip(),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            llm_timeout=float(os.getenv("LLM_TIMEOUT", "30")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
            llm_decompose_max_tokens=int(os.getenv("LLM_DECOMPOSE_MAX_TOKENS", "4096")),
            llm_thinking=os.getenv("LLM_THINKING", "").strip().lower(),
            db_path=_resolve_db_path(os.getenv("LIGHTSTEP_DB", "lightstep.db")),
            fast_threshold=float(os.getenv("FAST_THRESHOLD", "15")),
            slow_threshold=float(os.getenv("SLOW_THRESHOLD", "90")),
        )


settings = Settings.from_env()
