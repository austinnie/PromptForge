# handlers/__init__.py
"""处理器模块"""

from .base import BaseHandler
from .text_to_image import TextToImageHandler
from .image_to_image import ImageToImageHandler
from .couple_handler import CoupleHandler
from .multi_person_handler import MultiPersonHandler
from .chat_handler import ChatHandler
from .video_handler import VideoHandler  # ✅ 新增

__all__ = [
    'BaseHandler',
    'TextToImageHandler',
    'ImageToImageHandler',
    'CoupleHandler',
    'MultiPersonHandler',
    'ChatHandler',
    'VideoHandler',  # ✅ 新增

]