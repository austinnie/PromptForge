# providers/base.py
"""Provider 统一接口。

设计取舍：
  - 用 dataclass 传参而不是一堆 kwargs，签名自文档化
  - 只定义最小必需方法，扩展能力（视频/音频/视觉）单独 Protocol
  - from_config 作为类方法，让 create() 无需知道各 provider 的 __init__ 签名
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable, Optional, Any

from PIL import Image


# ============================================================
# 请求对象
# ============================================================

@dataclass
class ImageRequest:
    """统一图像生成请求。文生图 / 图生图共用。"""
    prompt: str
    negative: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 25
    cfg: float = 7.5
    seed: Optional[int] = None
    # 图生图时填写
    reference: Optional[Image.Image] = None
    reference_list: Optional[list[Image.Image]] = None
    strength: float = 0.7


@dataclass
class VideoRequest:
    prompt: str
    image: Optional[Image.Image] = None
    image_list: Optional[list[Image.Image]] = None
    duration: int = 10
    width: int = 768
    height: int = 768
    seed: Optional[int] = None
    # keyframe 模式
    first_frame_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    mode: Optional[str] = None  # text / keyframe / reference
    callback_url: Optional[str] = None


@dataclass
class AudioRequest:
    text: str
    voice: str = "nova"
    output_format: str = "mp3"
    duration: Optional[float] = None

@dataclass
class TextRequest:
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False

@runtime_checkable
class TextProvider(Protocol):
    """文本生成/对话能力"""
    provider_name: str

    def chat(self, req: TextRequest) -> str: ...
    
# ============================================================
# Provider 协议
# ============================================================

@runtime_checkable
class ImageProvider(Protocol):
    """图像生成能力"""
    provider_name: str

    def text_to_image(self, req: ImageRequest) -> Image.Image: ...

    def image_to_image(self, req: ImageRequest) -> Image.Image: ...


@runtime_checkable
class VideoProvider(Protocol):
    """视频生成能力"""
    provider_name: str

    def video_generation(self, req: VideoRequest) -> dict: ...

    def wait_for_video(self, video_id: str, **kw) -> str: ...


@runtime_checkable
class AudioProvider(Protocol):
    """音频生成能力"""
    provider_name: str

    def generate_audio(self, req: AudioRequest) -> bytes: ...


@runtime_checkable
class VisionProvider(Protocol):
    """视觉理解能力"""
    provider_name: str

    def image_to_text(self, image: Image.Image, prompt: str, **kw) -> str: ...


# ============================================================
# 可选基类（便于适配器少写样板）
# ============================================================

class BaseProvider:
    """适配器可选基类。不是 Protocol 的替代品，只是提供默认实现。"""

    provider_name: str = "unknown"

    @classmethod
    def from_config(cls, config: dict) -> "BaseProvider":
        """从配置字典构造实例。子类覆盖 __init__ 时应保持兼容。"""
        return cls(**config)

    def get_name(self) -> str:
        return f"{self.provider_name} ({self.provider_name})"

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.provider_name}>"