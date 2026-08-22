# config/settings.py
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ✅ 添加这行：加载 .env 文件
from dotenv import load_dotenv

# ✅ 加载 .env 文件
load_dotenv()

# ✅ 添加这行：打印加载状态（调试用）
print(f"📁 加载 .env: SD_MODEL_PATH = {os.getenv('SD_MODEL_PATH', '未设置')}")


@dataclass
class Settings:
    """全局配置"""
    
    # 项目根目录
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    
    # --- 模型路径 ---
    model_path: str = os.getenv("SD_MODEL_PATH", "")
    lora_path: str = os.getenv("LORA_PATH", "")
    vae_path: str = os.getenv("VAE_PATH", "")
    
    # --- LLM 配置 ---
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    
    # --- 生成参数 ---
    default_steps: int = 20
    default_cfg: float = 7.5
    default_strength: float = 0.35
    default_width: int = 512
    default_height: int = 768
    
    # --- 输出 ---
    output_dir: Path = field(default_factory=lambda: Path("output"))
    
    # --- 安全 ---
    safe_mode: bool = os.getenv("SAFE_MODE", "true").lower() == "true"
    
    def __post_init__(self):
        self.output_dir.mkdir(exist_ok=True)
        # ✅ 添加调试信息
        print(f"📦 模型路径: {self.model_path}")
        print(f"   ✅ 存在: {os.path.exists(self.model_path) if self.model_path else 'False'}")
    
    def get_model_path(self) -> Optional[str]:
        """获取有效模型路径"""
        if self.model_path and os.path.exists(self.model_path):
            return self.model_path
        return None


# 全局单例
settings = Settings()