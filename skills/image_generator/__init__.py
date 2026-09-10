"""
image_generator - 图像生成 Skill

支持文生图、图生图，可切换多个 API 提供商（Agnes、Pollinations、HuggingFace 等）
"""

from .skill import ImageGenerator

__all__ = ["ImageGenerator"]