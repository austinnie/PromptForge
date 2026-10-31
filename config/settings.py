# config/settings.py
"""PromptForge 全局配置。

P3 改造版：
  - provider 配置全部下沉到 providers.registry（config_schema）
  - settings.py 只保留"业务层真正会用到的核心字段"
  - get_provider_config 优先走 registry.load_config

行数：约 400 → 约 230
删除：tongyi / yige / hunyuan / hf / replicate / stability /
      free_multimodal_proxy / freellmapi / siliconflow / openrouter 等
      未被业务层引用的字段
      以及硬编码的 get_provider_info dict
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROVIDER_CACHE: dict[str, dict] = {}

DEFAULT_LOCAL_MODEL_ID = "sd_v1_5_aiiiiii01_v10"

# ------------------------------------------------------------
# 加载 .env
# ------------------------------------------------------------
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

if os.getenv("PF_DEBUG_ENV", "0") == "1":
    print(f"📂 .env 文件路径: {_ENV_PATH}")
    print(f"📂 .env 文件是否存在: {_ENV_PATH.exists()}")
    print(f"📂 VIDEO_DURATION 原始值: {os.getenv('VIDEO_DURATION')}")


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or not v.strip():
        return default
    try:
        return int(v)
    except ValueError:
        logger.warning(f"⚠️ {key}={v!r} 无法解析为 int，使用默认 {default}")
        return default


def _env_float(key: str, default: float) -> float:
    v = os.getenv(key)
    if v is None or not v.strip():
        return default
    try:
        return float(v)
    except ValueError:
        logger.warning(f"⚠️ {key}={v!r} 无法解析为 float，使用默认 {default}")
        return default


def _env_list(key: str, default: List[str]) -> List[str]:
    v = os.getenv(key, "").strip()
    if not v:
        return list(default)
    return [item.strip() for item in v.split(",") if item.strip()]


@dataclass
class Settings:
    """全局配置"""

    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # ============================================================
    # 本地模型
    # ============================================================
    model_path: str = field(default_factory=lambda: os.getenv("SD_MODEL_PATH", ""))
    lora_path: str = field(default_factory=lambda: os.getenv("LORA_PATH", ""))
    vae_path: str = field(default_factory=lambda: os.getenv("VAE_PATH", ""))

    # ============================================================
    # LLM 通用配置（LLMClient 使用）
    # ============================================================
    llm_enabled: bool = field(default_factory=lambda: _env_bool("LLM_ENABLED", "true"))
    llm_backends: List[str] = field(
        default_factory=lambda: _env_list("LLM_BACKENDS", ["agnes", "ollama"])
    )
    llm_timeout: int = field(default_factory=lambda: _env_int("LLM_TIMEOUT", 120))
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.7))
    llm_max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 2048))

    ollama_url: str = field(
        default_factory=lambda: (
            os.getenv("OLLAMA_URL")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
    )
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"))
    ollama_temperature: float = field(
        default_factory=lambda: _env_float("OLLAMA_TEMPERATURE", 0.7)
    )
    ollama_max_tokens: int = field(default_factory=lambda: _env_int("OLLAMA_MAX_TOKENS", 2048))
    ollama_dynamic_prompt_enabled: bool = field(
        default_factory=lambda: _env_bool("OLLAMA_DYNAMIC_PROMPT_ENABLED", "true")
    )
    ollama_num_parallel: int = field(
        default_factory=lambda: _env_int("OLLAMA_NUM_PARALLEL", 2)
    )

    # GitHub 日报专属 LLM
    gh_daily_llm_backends: List[str] = field(
        default_factory=lambda: _env_list("GH_DAILY_LLM_BACKENDS", ["agnes", "ollama"])
    )
    gh_daily_llm_timeout: int = field(
        default_factory=lambda: _env_int("GH_DAILY_LLM_TIMEOUT", 120)
    )
    gh_daily_llm_temperature: float = field(
        default_factory=lambda: _env_float("GH_DAILY_LLM_TEMPERATURE", 0.7)
    )
    gh_daily_llm_max_tokens: int = field(
        default_factory=lambda: _env_int("GH_DAILY_LLM_MAX_TOKENS", 2048)
    )

    # ============================================================
    # 生成模式
    # ============================================================
    generation_mode: str = field(default_factory=lambda: os.getenv("GENERATION_MODE", "local"))
    api_provider: str = field(default_factory=lambda: os.getenv("API_PROVIDER", "pollinations"))

    # ============================================================
    # Agnes（被 llm_client / video_generator / wechat_formatter / image_curator 直接引用）
    # 其余 provider 的配置请用 settings.get_provider_config(name)
    # ============================================================
    agnes_api_key: str = field(default_factory=lambda: os.getenv("AGNES_API_KEY", ""))
    agnes_image_model: str = field(
        default_factory=lambda: os.getenv("AGNES_IMAGE_MODEL", "agnes-image-2.5-flash")
    )
    agnes_text_model: str = field(
        default_factory=lambda: os.getenv("AGNES_TEXT_MODEL", "agnes-2.5-flash")
    )
    agnes_video_model: str = field(
        default_factory=lambda: os.getenv("AGNES_VIDEO_MODEL", "agnes-video-2.5-flash")
    )
    agnes_vision_model: str = field(
        default_factory=lambda: os.getenv("AGNES_VISION_MODEL", "agnes-2.5-flash")
    )
    agnes_base_url: str = field(
        default_factory=lambda: os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
    )

    # ============================================================
    # 生成参数
    # ============================================================
    default_steps: int = field(default_factory=lambda: _env_int("DEFAULT_STEPS", 20))
    default_cfg: float = field(default_factory=lambda: _env_float("DEFAULT_CFG", 7.5))
    default_strength: float = field(default_factory=lambda: _env_float("DEFAULT_STRENGTH", 0.35))
    default_width: int = field(default_factory=lambda: _env_int("DEFAULT_WIDTH", 512))
    default_height: int = field(default_factory=lambda: _env_int("DEFAULT_HEIGHT", 768))

    # ============================================================
    # 视频
    # ============================================================
    video_duration: int = field(default_factory=lambda: _env_int("VIDEO_DURATION", 60))
    video_segment_duration: int = field(
        default_factory=lambda: _env_int("VIDEO_SEGMENT_DURATION", 10)
    )
    video_auto_merge: bool = field(
        default_factory=lambda: _env_bool("VIDEO_AUTO_MERGE", "true")
    )

    # ============================================================
    # 输出
    # ============================================================
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "output"))
    )

    # ============================================================
    # 安全
    # ============================================================
    safe_mode: bool = field(default_factory=lambda: _env_bool("SAFE_MODE", "true"))
    enable_safety_check: bool = field(
        default_factory=lambda: _env_bool("ENABLE_SAFETY_CHECK", "true")
    )

    # ============================================================
    # 文章配图
    # ============================================================
    article_image_engine: str = field(
        default_factory=lambda: os.getenv("ARTICLE_IMAGE_ENGINE", "agnes")
    )

    # ============================================================
    # 微信公众号
    # ============================================================
    wechat_app_id: str = field(default_factory=lambda: os.getenv("WECHAT_APP_ID", ""))
    wechat_app_secret: str = field(default_factory=lambda: os.getenv("WECHAT_APP_SECRET", ""))
    wechat_author: str = field(default_factory=lambda: os.getenv("WECHAT_AUTHOR", ""))
    wechat_default_theme: str = field(
        default_factory=lambda: os.getenv("WECHAT_DEFAULT_THEME", "newspaper")
    )
    wechat_output_dir: str = field(
        default_factory=lambda: os.getenv("WECHAT_OUTPUT_DIR", "./output/wechat")
    )

    # ============================================================
    # 新闻简报
    # ============================================================
    news_enabled: bool = field(default_factory=lambda: _env_bool("NEWS_ENABLED", "true"))
    news_output_dir: str = field(
        default_factory=lambda: os.getenv("NEWS_OUTPUT_DIR", "./output/news")
    )
    news_feeds: List[str] = field(
        default_factory=lambda: _env_list(
            "NEWS_FEEDS", ["world", "technology", "business", "china", "science"]
        )
    )
    news_max_articles: int = field(default_factory=lambda: _env_int("NEWS_MAX_ARTICLES", 15))
    news_validate_feeds: bool = field(
        default_factory=lambda: _env_bool("NEWS_VALIDATE_FEEDS", "true")
    )
    news_enable_summary: bool = field(
        default_factory=lambda: _env_bool("NEWS_ENABLE_SUMMARY", "true")
    )
    news_summary_model: str = field(
        default_factory=lambda: os.getenv("NEWS_SUMMARY_MODEL", "qwen2.5:1.5b")
    )
    news_cache_ttl: int = field(default_factory=lambda: _env_int("NEWS_CACHE_TTL", 3600))
    news_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "NEWS_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
    )
    news_llm_backends: List[str] = field(
        default_factory=lambda: _env_list("NEWS_LLM_BACKENDS", [])
    )

    # ============================================================
    # 初始化
    # ============================================================

    def __post_init__(self):
        if not self.output_dir.is_absolute():
            self.output_dir = self.BASE_DIR / self.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"video_segment_duration={self.video_segment_duration}")
        logger.debug(f"安全检测: {'启用' if self.enable_safety_check else '禁用'}")
        logger.debug(f"LLM 后端: {self.llm_backends}")

    # ============================================================
    # 工具方法
    # ============================================================

    def get_model_path(self) -> Optional[str]:
        if self.model_path and os.path.exists(self.model_path):
            return self.model_path
        return None

    def get_provider_info(self, provider: str) -> dict:
        """获取 provider 元信息（从 registry 读，P3 改造后不再硬编码）"""
        try:
            from providers import get_meta
            return get_meta(provider)
        except Exception:
            return {}

    def get_provider_config(self, name: str) -> dict:
        """获取 provider 配置。

        优先级：
          1. providers.registry.load_config(name) —— 按 config_schema 从 env 读
          2. 回退：扫 {NAME}_* 环境变量（兼容无 schema 的 provider）

        结果进程内缓存；修改 .env 后调 clear_provider_cache()。
        """
        if name in _PROVIDER_CACHE:
            return _PROVIDER_CACHE[name]

        cfg: dict = {}

        # 优先走 registry schema
        try:
            from providers.registry import load_config
            cfg = load_config(name) or {}
        except Exception as e:
            logger.debug(f"load_config({name}) 失败，回退到扫 env: {e}")

        # 回退：扫 {NAME}_*
        if not cfg:
            prefix = f"{name.upper()}_"
            for key, value in os.environ.items():
                if not key.startswith(prefix):
                    continue
                short = key[len(prefix):].lower()
                cfg[short] = value
                cfg[key] = value

        _PROVIDER_CACHE[name] = cfg
        return cfg

    def clear_provider_cache(self) -> None:
        """清空 provider 配置缓存（改 .env 后调用）。"""
        _PROVIDER_CACHE.clear()


settings = Settings()