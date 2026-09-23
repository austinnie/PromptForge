# config/settings.py
"""PromptForge 全局配置。

设计要点：
  - 所有 os.getenv 用 field(default_factory=...) 延迟求值，
    避免 dataclass 类体求值时 .env 尚未加载
  - output_dir 相对路径按 BASE_DIR 解析，避免 CWD 依赖
  - Ollama 地址兼容 OLLAMA_URL / OLLAMA_HOST 双名
  - 补齐 LLMClient 相关字段（LLM_BACKENDS 等）
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# 加载 .env
# ------------------------------------------------------------
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

# 调试开关：设置 PF_DEBUG_ENV=1 才打印加载信息
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

    # Ollama 地址：优先 OLLAMA_URL，回退 OLLAMA_HOST
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

    # GitHub 日报专属 LLM 配置
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
    # 生成模式 / 提供商
    # ============================================================
    generation_mode: str = field(default_factory=lambda: os.getenv("GENERATION_MODE", "local"))
    api_provider: str = field(default_factory=lambda: os.getenv("API_PROVIDER", "pollinations"))

    # ============================================================
    # 图像 API 提供商
    # ============================================================
    # ----- 通义万相 -----
    tongyi_api_key: str = field(default_factory=lambda: os.getenv("TONGYI_API_KEY", ""))
    tongyi_model: str = field(default_factory=lambda: os.getenv("TONGYI_MODEL", "wanx-v1"))
    tongyi_base_url: str = field(default_factory=lambda: os.getenv("TONGYI_BASE_URL", ""))

    # ----- 文心一格 -----
    yige_api_key: str = field(default_factory=lambda: os.getenv("YIGE_API_KEY", ""))
    yige_secret_key: str = field(default_factory=lambda: os.getenv("YIGE_SECRET_KEY", ""))

    # ----- 腾讯混元 -----
    hunyuan_secret_id: str = field(default_factory=lambda: os.getenv("HUNYUAN_SECRET_ID", ""))
    hunyuan_secret_key: str = field(default_factory=lambda: os.getenv("HUNYUAN_SECRET_KEY", ""))

    # ----- HuggingFace -----
    hf_api_token: str = field(default_factory=lambda: os.getenv("HF_API_TOKEN", ""))
    hf_model: str = field(default_factory=lambda: os.getenv("HF_MODEL", "sdxl"))

    # ----- Pollinations -----
    pollinations_api_key: str = field(default_factory=lambda: os.getenv("POLLINATIONS_API_KEY", ""))
    pollinations_model: str = field(
        default_factory=lambda: os.getenv("POLLINATIONS_MODEL", "black-forest-labs/flux.1-schnell")
    )
    pollinations_audio_model: str = field(
        default_factory=lambda: os.getenv(
            "POLLINATIONS_AUDIO_MODEL", "community/NamanSoni78/aura-2-amalthea-en"
        )
    )
    pollinations_video_model: str = field(
        default_factory=lambda: os.getenv("POLLINATIONS_VIDEO_MODEL", "")
    )

    # ----- Agnes AI -----
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

    # ----- Free API -----
    freeapi_model: str = field(default_factory=lambda: os.getenv("FREEAPI_MODEL", "qwen3.7-plus"))

    # ----- Replicate -----
    replicate_api_token: str = field(default_factory=lambda: os.getenv("REPLICATE_API_TOKEN", ""))
    replicate_model: str = field(
        default_factory=lambda: os.getenv("REPLICATE_MODEL", "stability-ai/stable-diffusion")
    )

    # ----- Stability AI -----
    stability_api_key: str = field(default_factory=lambda: os.getenv("STABILITY_API_KEY", ""))
    stability_model: str = field(
        default_factory=lambda: os.getenv("STABILITY_MODEL", "stable-diffusion-xl-1024-v1-0")
    )

    # ----- Free Multimodal Proxy -----
    free_multimodal_proxy_url: str = field(
        default_factory=lambda: os.getenv("FREE_MULTIMODAL_PROXY_URL", "http://localhost:8080/v1")
    )
    free_multimodal_proxy_model: str = field(
        default_factory=lambda: os.getenv("FREE_MULTIMODAL_PROXY_MODEL", "zimage")
    )
    free_multimodal_proxy_token: str = field(
        default_factory=lambda: os.getenv("FREE_MULTIMODAL_PROXY_TOKEN", "")
    )

    # ----- FreeLLMAPI -----
    freellmapi_url: str = field(
        default_factory=lambda: os.getenv("FREELLMAPI_URL", "http://localhost:3000/v1")
    )
    freellmapi_model: str = field(default_factory=lambda: os.getenv("FREELLMAPI_MODEL", "auto"))
    freellmapi_key: str = field(
        default_factory=lambda: os.getenv("FREELLMAPI_KEY", "freellmapi")
    )

    # ----- 硅基流动 -----
    siliconflow_api_key: str = field(default_factory=lambda: os.getenv("SILICONFLOW_API_KEY", ""))
    siliconflow_model: str = field(
        default_factory=lambda: os.getenv("SILICONFLOW_MODEL", "sd-turbo")
    )

    # ----- OpenRouter -----
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "bytedance-seed/seedream-4.5")
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
    # 视频生成
    # ============================================================
    # 目标时长（秒），超长会自动分段拼接
    video_duration: int = field(default_factory=lambda: _env_int("VIDEO_DURATION", 60))
    # 单段时长（秒）
    video_segment_duration: int = field(
        default_factory=lambda: _env_int("VIDEO_SEGMENT_DURATION", 10)
    )
    # 是否自动循环拼接（默认开启）
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
    # 文章配图引擎
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

    # ============================================================
    # 初始化后处理
    # ============================================================

    def __post_init__(self):
        # output_dir 相对路径按 BASE_DIR 解析
        if not self.output_dir.is_absolute():
            self.output_dir = self.BASE_DIR / self.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 调试日志（改成 logger.debug，避免每次实例化刷屏）
        logger.debug(f"Settings.video_segment_duration = {self.video_segment_duration}")
        logger.debug(f"Settings.video_duration = {self.video_duration}")
        logger.debug(f"安全检测开关: {'启用' if self.enable_safety_check else '禁用'}")
        logger.debug(f"LLM 后端: {self.llm_backends}")
        logger.debug(f"Ollama 地址: {self.ollama_url}")

    # ============================================================
    # 工具方法
    # ============================================================

    def get_model_path(self) -> Optional[str]:
        if self.model_path and os.path.exists(self.model_path):
            return self.model_path
        return None

    def get_api_config(self) -> dict:
        """获取所有 API 配置（供 create_engine 使用）"""
        return {
            "tongyi": {
                "TONGYI_API_KEY": self.tongyi_api_key,
                "TONGYI_MODEL": self.tongyi_model,
                "TONGYI_BASE_URL": self.tongyi_base_url,
            },
            "yige": {
                "YIGE_API_KEY": self.yige_api_key,
                "YIGE_SECRET_KEY": self.yige_secret_key,
            },
            "hunyuan": {
                "HUNYUAN_SECRET_ID": self.hunyuan_secret_id,
                "HUNYUAN_SECRET_KEY": self.hunyuan_secret_key,
            },
            "huggingface": {
                "HF_API_TOKEN": self.hf_api_token,
                "HF_MODEL": self.hf_model,
            },
            "pollinations": {
                "POLLINATIONS_API_KEY": self.pollinations_api_key,
                "POLLINATIONS_MODEL": self.pollinations_model,
                "POLLINATIONS_VIDEO_MODEL": self.pollinations_video_model,
                "POLLINATIONS_AUDIO_MODEL": self.pollinations_audio_model,
            },
            "agnes": {
                "AGNES_API_KEY": self.agnes_api_key,
                "AGNES_IMAGE_MODEL": self.agnes_image_model,
                "AGNES_TEXT_MODEL": self.agnes_text_model,
                "AGNES_VIDEO_MODEL": self.agnes_video_model,
                "AGNES_VISION_MODEL": self.agnes_vision_model,
                "AGNES_BASE_URL": self.agnes_base_url,
            },
            "freeapi": {
                "FREEAPI_MODEL": self.freeapi_model,
            },
            "replicate": {
                "REPLICATE_API_TOKEN": self.replicate_api_token,
                "REPLICATE_MODEL": self.replicate_model,
            },
            "stability": {
                "STABILITY_API_KEY": self.stability_api_key,
                "STABILITY_MODEL": self.stability_model,
            },
            "free_multimodal_proxy": {
                "FREE_MULTIMODAL_PROXY_URL": self.free_multimodal_proxy_url,
                "FREE_MULTIMODAL_PROXY_MODEL": self.free_multimodal_proxy_model,
                "FREE_MULTIMODAL_PROXY_TOKEN": self.free_multimodal_proxy_token,
            },
            "freellmapi": {
                "FREELLMAPI_URL": self.freellmapi_url,
                "FREELLMAPI_MODEL": self.freellmapi_model,
                "FREELLMAPI_KEY": self.freellmapi_key,
            },
            "siliconflow": {
                "SILICONFLOW_API_KEY": self.siliconflow_api_key,
                "SILICONFLOW_MODEL": self.siliconflow_model,
            },
            "openrouter": {
                "OPENROUTER_API_KEY": self.openrouter_api_key,
                "OPENROUTER_MODEL": self.openrouter_model,
            },
        }

    def get_provider_info(self, provider: str) -> dict:
        """获取特定提供商的信息"""
        providers = {
            "tongyi": {
                "name": "通义万相 (阿里云百炼)",
                "requires_key": True,
                "free": False,
                "description": "阿里云百炼平台，需要 API Key",
            },
            "pollinations": {
                "name": "Pollinations AI",
                "requires_key": True,
                "free": True,
                "description": "免费，需注册获取 API Key",
            },
            "agnes": {
                "name": "Agnes AI",
                "requires_key": True,
                "free": True,
                "description": "无限期免费，需注册获取 API Key",
            },
            "huggingface": {
                "name": "HuggingFace",
                "requires_key": True,
                "free": True,
                "description": "免费但有限速，需 API Token",
            },
            "yige": {
                "name": "文心一格 (百度)",
                "requires_key": True,
                "free": False,
                "description": "百度文心一格，按量付费",
            },
            "hunyuan": {
                "name": "腾讯混元",
                "requires_key": True,
                "free": False,
                "description": "腾讯混元，按量付费",
            },
            "replicate": {
                "name": "Replicate",
                "requires_key": True,
                "free": False,
                "description": "按量付费，支持真正的图生图",
            },
            "stability": {
                "name": "Stability AI",
                "requires_key": True,
                "free": False,
                "description": "按量付费，支持真正的图生图",
            },
            "freeapi": {
                "name": "Free API",
                "requires_key": False,
                "free": True,
                "description": "社区免费代理，稳定性较差",
            },
            "siliconflow": {
                "name": "硅基流动",
                "requires_key": True,
                "free": False,
                "description": "国内平台，注册获取 Key",
            },
            "openrouter": {
                "name": "OpenRouter",
                "requires_key": True,
                "free": False,
                "description": "聚合 30+ 模型",
            },
        }
        return providers.get(provider, {})


settings = Settings()