# core/prompt_builder.py
from typing import Dict, List, Optional


class PromptBuilder:
    """提示词构建器"""
    
    QUALITY_WORDS = ['masterpiece', 'best quality', '8k', 'highly detailed']
    NEGATIVE_TEMPLATE = "worst quality, low quality, ugly, deformed, blurry, bad anatomy, watermark, text"
    
    def build(self, intent: Dict, keywords: Dict) -> str:
        """构建完整提示词"""
        parts = []
        
        # 1. 质量词
        parts.extend(self.QUALITY_WORDS)
        
        # 2. 性别
        genders = keywords.get("genders", [])
        if genders:
            parts.append(genders[0])
        
        # 3. 主体描述
        if intent.get("prompt"):
            parts.append(intent["prompt"])
        
        # 4. 场景
        scenes = keywords.get("scenes", [])
        if scenes:
            parts.append(scenes[0])
        
        # 5. 风格
        styles = keywords.get("styles", [])
        if styles:
            parts.append(styles[0])
        
        # 6. 颜色
        colors = keywords.get("colors", [])
        if colors:
            parts.append(colors[0])
        
        return ", ".join(parts)
    
    def build_negative(self, custom: Optional[str] = None) -> str:
        """构建负面提示词"""
        if custom:
            return f"{self.NEGATIVE_TEMPLATE}, {custom}"
        return self.NEGATIVE_TEMPLATE
    
    def enhance_with_context(self, prompt: str, context: Dict) -> str:
        """基于上下文增强提示词"""
        if not prompt or not context:
            return prompt
        
        parts = [prompt]
        
        # 添加上下文偏好
        if context.get("style"):
            parts.append(context["style"])
        if context.get("scene"):
            parts.append(context["scene"])
        
        return ", ".join(parts)