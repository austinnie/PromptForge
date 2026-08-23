# config/settings.py
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """全局配置"""
    
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    
    # --- 模型路径 ---
    model_path: str = os.getenv("SD_MODEL_PATH", "")
    lora_path: str = os.getenv("LORA_PATH", "")
    vae_path: str = os.getenv("VAE_PATH", "")
    
    # --- LLM 配置 ---
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    
    # --- API 配置 ---
    # 图像生成模式: "local" 或 "api"
    generation_mode: str = os.getenv("GENERATION_MODE", "local")
    
    # 默认 API 提供商
    api_provider: str = os.getenv("API_PROVIDER", "pollinations")
    
    # ----- 通义万相 (阿里云百炼) -----
    tongyi_api_key: str = os.getenv("TONGYI_API_KEY", "")
    tongyi_model: str = os.getenv("TONGYI_MODEL", "wan2.1-t2i-plus")
    tongyi_base_url: str = os.getenv("TONGYI_BASE_URL", "")
    
    # ----- 文心一格 (百度) -----
    yige_api_key: str = os.getenv("YIGE_API_KEY", "")
    yige_secret_key: str = os.getenv("YIGE_SECRET_KEY", "")
    
    # ----- 腾讯混元 -----
    hunyuan_secret_id: str = os.getenv("HUNYUAN_SECRET_ID", "")
    hunyuan_secret_key: str = os.getenv("HUNYUAN_SECRET_KEY", "")
    
    # ----- HuggingFace -----
    hf_api_token: str = os.getenv("HF_API_TOKEN", "")
    hf_model: str = os.getenv("HF_MODEL", "sdxl")
    
    # ----- Pollinations AI (完全免费，无需 API Key) -----
    pollinations_model: str = os.getenv("POLLINATIONS_MODEL", "flux")
    
    # ----- Agnes AI (需注册获取 API Key) -----
    agnes_api_key: str = os.getenv("AGNES_API_KEY", "")
    agnes_model: str = os.getenv("AGNES_MODEL", "flux")
    
    # --- 生成参数 ---
    default_steps: int = int(os.getenv("DEFAULT_STEPS", "20"))
    default_cfg: float = float(os.getenv("DEFAULT_CFG", "7.5"))
    default_strength: float = float(os.getenv("DEFAULT_STRENGTH", "0.35"))
    default_width: int = int(os.getenv("DEFAULT_WIDTH", "512"))
    default_height: int = int(os.getenv("DEFAULT_HEIGHT", "768"))
    
    # --- 输出 ---
    output_dir: Path = field(default_factory=lambda: Path("output"))
    
    # --- 安全 ---
    safe_mode: bool = os.getenv("SAFE_MODE", "true").lower() == "true"
    
    def __post_init__(self):
        self.output_dir.mkdir(exist_ok=True)
    
    def get_model_path(self) -> Optional[str]:
        if self.model_path and os.path.exists(self.model_path):
            return self.model_path
        return None
    
    def get_api_config(self) -> dict:
        """获取 API 配置"""
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
                "POLLINATIONS_MODEL": self.pollinations_model,
            },
            "agnes": {
                "AGNES_API_KEY": self.agnes_api_key,
                "AGNES_MODEL": self.agnes_model,
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
                "requires_key": False,
                "free": True,
                "description": "完全免费，无需注册，开箱即用",
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
        }
        return providers.get(provider, {})


settings = Settings()