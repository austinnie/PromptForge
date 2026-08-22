# api_engines/base.py
"""API 图像生成引擎基类"""

from abc import ABC, abstractmethod
from PIL import Image
from typing import Optional, Dict, Any


class BaseEngine(ABC):
    """API 图像生成引擎基类"""
    
    @abstractmethod
    def generate_single(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: Optional[int] = None,
    ) -> Image.Image:
        """生成单张图片"""
        pass
    
    @abstractmethod
    def get_usage(self) -> Dict[str, Any]:
        """获取使用量信息"""
        pass
    
    def get_name(self) -> str:
        """获取引擎名称"""
        return self.__class__.__name__.replace('Engine', '')