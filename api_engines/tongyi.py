# core/api_engines/tongyi.py
"""通义万相 API 图像生成引擎"""

import base64
import io
from PIL import Image

try:
    import dashscope
    from dashscope import ImageSynthesis
except ImportError:
    dashscope = None

import random 

class TongyiEngine:
    """通义万相 API 引擎"""
    
    def __init__(self, api_key: str, model: str = "wanx-v1"):
        self.api_key = api_key
        self.model = model
        
        if dashscope:
            dashscope.api_key = api_key
        
        self.supported_sizes = [
            "512*512", "1024*1024", "1024*768", "768*1024",
            "1280*720", "720*1280", "1280*768", "768*1280"
        ]
    
    def generate_single(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """生成单张图片"""

        if seed is None:
            seed = random.randint(1, 2**32 - 1)
    
        if not dashscope:
            raise ImportError("请安装 dashscope: pip install dashscope")
        
        if not self.api_key:
            raise ValueError("请设置 TONGYI_API_KEY")
        
        size = f"{width}*{height}"
        if size not in self.supported_sizes:
            size = "1024*1024"
            print(f"   ⚠️ 通义万相不支持 {width}x{height}，使用 1024x1024")
        
        response = ImageSynthesis.call(
            model=self.model,
            prompt=prompt,
            negative_prompt=negative or "worst quality, low quality",
            n=1,
            size=size,
            step=steps,
            cfg_scale=cfg,
            seed=seed,
        )
        
        if response.status_code != 200:
            raise Exception(f"通义万相 API 调用失败: {response.message}")
        
        image_data = response.output.results[0].url
        
        if image_data.startswith("data:image"):
            import re
            base64_data = re.sub(r"^data:image/.+;base64,", "", image_data)
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes))
        
        import requests
        img_response = requests.get(image_data, timeout=30)
        return Image.open(io.BytesIO(img_response.content))