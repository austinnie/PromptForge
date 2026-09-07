"""
Stability AI API 图像生成引擎 - 支持真正的图生图
需要 API Key，按量付费
"""

import os
import requests
from PIL import Image
import io
import base64
from typing import Optional, Dict, Any


class StabilityEngine:
    """Stability AI API 引擎（支持图生图）"""
    
    def __init__(self, api_key: str, model: str = "stable-diffusion-xl-1024-v1-0"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.stability.ai/v1"
        
        if not self.api_key:
            print("⚠️ 未设置 STABILITY_API_KEY，请从 https://platform.stability.ai/account/keys 获取")
        
        print(f"🔍 Stability AI 引擎初始化")
        print(f"🔍 模型: {self.model}")
    
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
        """文生图"""
        response = requests.post(
            f"{self.base_url}/generation/{self.model}/text-to-image",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "text_prompts": [{"text": prompt}],
                "cfg_scale": cfg,
                "steps": steps,
                "width": width,
                "height": height,
                "seed": seed,
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Stability API 失败: {response.text}")
        
        data = response.json()
        image_base64 = data["artifacts"][0]["base64"]
        image_bytes = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(image_bytes))
    
    def image_to_image(
        self,
        prompt: str,
        image: Image.Image,
        strength: float = 0.5,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """图生图 - 真正的 img2img"""
        # 将图片转为 base64
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        response = requests.post(
            f"{self.base_url}/generation/{self.model}/image-to-image",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "text_prompts": [{"text": prompt}],
                "init_image": img_base64,
                "image_strength": strength,
                "cfg_scale": cfg,
                "steps": steps,
                "seed": seed,
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Stability API 失败: {response.text}")
        
        data = response.json()
        image_base64 = data["artifacts"][0]["base64"]
        image_bytes = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(image_bytes))
    
    def get_usage(self) -> Dict[str, Any]:
        return {"info": "请登录 Stability AI 控制台查看使用量"}
    
    def get_name(self) -> str:
        return f"Stability AI ({self.model})"
    
    def get_model(self) -> str:
        return self.model