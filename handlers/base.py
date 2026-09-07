# handlers/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from PIL import Image
import os
from datetime import datetime


class BaseHandler(ABC):
    """处理器基类"""
    
    def __init__(self, app):
        self.app = app
        self.llm = app.llm if hasattr(app, 'llm') else None
        self.context = app.context if hasattr(app, 'context') else None
    
    @abstractmethod
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理意图"""
        pass
    
    def _reply(self, content: str):
        if hasattr(self.app, '_append_message'):
            self.app._append_message("assistant", content)
        else:
            print(f"[assistant] {content}")

    def _update_status(self, msg: str):
        if hasattr(self.app, 'status_var') and self.app.status_var is not None:
            try:
                self.app.status_var.set(msg)
            except Exception:
                print(f"[STATUS] {msg}")
        else:
            print(f"[STATUS] {msg}")
    
    def _get_pipeline(self):
        """获取Pipeline（子类可重写）"""
        if hasattr(self.app, 'pipe'):
            return self.app.pipe
        return None
    
    def _save_image(self, image: Image.Image, prompt: str, prefix: str = "chat") -> str:
        """保存图片"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in " _-") or "image"
        filename = f"{timestamp}_{prefix}_{safe_prompt}.png"
        
        output_dir = self.app.settings.output_dir
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        image.save(filepath)
        
        # 更新上下文
        if self.context:
            self.context.last_image = filepath
        
        return filepath
    
    # handlers/base.py

    def _ensure_model_loaded(self) -> bool:
        """确保模型已加载（仅本地模式）"""
        # ✅ 如果是 API 模式，跳过本地模型检查
        if self.app.settings.generation_mode == "api":
            return True
        
        if hasattr(self.app, 'is_model_loaded') and self.app.is_model_loaded:
            return True
        
        if hasattr(self.app, '_load_model'):
            self.app._load_model()
            # 等待加载完成（简单轮询）
            import time
            for _ in range(30):  # 最多等待 30 秒
                if self.app.is_model_loaded:
                    return True
                time.sleep(0.5)
            return self.app.is_model_loaded
        
        self._reply("⚠️ 模型未加载，请先加载模型")
        return False