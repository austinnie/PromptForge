# api_engines/replicate.py - 新建文件

import os
import requests
from PIL import Image
import io
import time
from typing import Optional

class ReplicateEngine:
    """Replicate API 图像生成引擎（支持图生图）"""
    
    def __init__(self, api_token: str, model: str = "stability-ai/stable-diffusion"):
        self.api_token = api_token
        self.model = model
        self.base_url = "https://api.replicate.com/v1"
    
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
        import base64
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }
        
        data = {
            "version": "stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf",
            "input": {
                "prompt": prompt,
                "image": f"data:image/png;base64,{img_base64}",
                "strength": strength,
                "num_outputs": 1,
                "num_inference_steps": steps,
                "guidance_scale": cfg,
                "seed": seed,
            }
        }
        
        # 创建预测
        response = requests.post(
            f"{self.base_url}/predictions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 201:
            raise Exception(f"Replicate 创建预测失败: {response.text}")
        
        result = response.json()
        prediction_url = result.get("urls", {}).get("get")
        
        # 轮询结果
        for _ in range(60):  # 最多等待 60 秒
            time.sleep(2)
            status_response = requests.get(prediction_url, headers=headers)
            status = status_response.json()
            
            if status.get("status") == "succeeded":
                image_url = status.get("output")[0]
                img_response = requests.get(image_url)
                return Image.open(io.BytesIO(img_response.content))
            elif status.get("status") == "failed":
                raise Exception(f"Replicate 生成失败: {status.get('error')}")
        
        raise Exception("Replicate 生成超时")