# core/context_manager.py
from typing import Dict, List, Optional
from datetime import datetime


class ContextManager:
    """对话上下文管理器"""
    
    def __init__(self):
        self.history: List[Dict] = []
        self.preferences: Dict = {
            "style": None,
            "scene": None,
            "gender": None,
            "quality": "high",
        }
        self.last_prompt: Optional[str] = None
        self.last_intent: Optional[str] = None
        self.last_image: Optional[str] = None
    
    def update(self, intent: Dict, result: Dict = None):
        """更新上下文"""
        self.last_intent = intent.get("type")
        self.last_prompt = intent.get("prompt")
        
        if result and result.get("image_path"):
            self.last_image = result["image_path"]
        
        keywords = intent.get("keywords", {})
        if keywords.get("styles"):
            self.preferences["style"] = keywords["styles"][0]
        if keywords.get("scenes"):
            self.preferences["scene"] = keywords["scenes"][0]
        if keywords.get("genders"):
            self.preferences["gender"] = keywords["genders"][0]
        
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "intent": intent,
            "result": result
        })
        # 保持历史记录不超过50条
        if len(self.history) > 50:
            self.history = self.history[-50:]
    
    def get_summary(self) -> str:
        """获取上下文摘要"""
        if not self.history:
            return ""
        
        prefs = []
        if self.preferences.get("style"):
            prefs.append(f"风格偏好: {self.preferences['style']}")
        if self.preferences.get("scene"):
            prefs.append(f"场景偏好: {self.preferences['scene']}")
        if self.preferences.get("gender"):
            prefs.append(f"性别偏好: {self.preferences['gender']}")
        
        summary = []
        if prefs:
            summary.append("📌 用户偏好: " + ", ".join(prefs))
        if self.last_prompt:
            summary.append(f"📝 上次提示词: {self.last_prompt[:50]}...")
        if len(self.history) > 0:
            summary.append(f"💬 已对话 {len(self.history)} 轮")
        
        return "\n".join(summary)
    
    def has_context(self) -> bool:
        return len(self.history) > 0 or self.last_prompt is not None
    
    def clear(self):
        self.history = []
        self.preferences = {"style": None, "scene": None, "gender": None, "quality": "high"}
        self.last_prompt = None
        self.last_intent = None
        self.last_image = None