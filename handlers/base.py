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
        """回复消息"""
        self.app._append_message("assistant", content)
    
    def _update_status(self, msg: str):
        """更新状态"""
        self.app.status_var.set(msg)
    
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
    
    def _ensure_model_loaded(self) -> bool:
        """确保模型已加载"""
        if hasattr(self.app, 'is_model_loaded') and self.app.is_model_loaded:
            return True
        
        if hasattr(self.app, '_load_model'):
            self.app._load_model()
            return self.app.is_model_loaded
        
        self._reply("⚠️ 模型未加载，请先加载模型")
        return False