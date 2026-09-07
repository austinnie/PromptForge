# handlers/__init__.py
"""处理器模块"""

from .base import BaseHandler
from .text_to_image import TextToImageHandler
from .image_to_image import ImageToImageHandler
from .couple_handler import CoupleHandler
from .chat_handler import ChatHandler
from .video_handler import VideoHandler  # ✅ 新增

__all__ = [
    'BaseHandler',
    'TextToImageHandler',
    'ImageToImageHandler',
    'CoupleHandler',
    'ChatHandler',
    'VideoHandler',  # ✅ 新增
]