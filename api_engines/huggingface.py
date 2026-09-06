# core/api_engines/huggingface.py
"""HuggingFace Inference API 图像生成引擎"""

import requests
from PIL import Image
import io
import time
import random 

class HuggingFaceEngine:
    """HuggingFace Inference API 引擎"""
    
    AVAILABLE_MODELS = {
        "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
        "sd3": "stabilityai/stable-diffusion-3.5-large",
        "flux": "black-forest-labs/FLUX.1-dev",
        "sd15": "runwayml/stable-diffusion-v1-5",
    }
    
    def __init__(self, api_token: str, model: str = "sdxl"):
        self.api_token = api_token
        self.model = self.AVAILABLE_MODELS.get(model, model)
        self.url = f"https://api-inference.huggingface.co/models/{self.model}"
        self.last_request_time = 0
        self.min_interval = 2
    
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

        if seed is None:
            seed = random.randint(1, 2**32 - 1)
    
        if not self.api_token:
            raise ValueError("请设置 HF_API_TOKEN")
        
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative or "worst quality, low quality",
                "num_inference_steps": steps,
                "guidance_scale": cfg,
                "width": width,
                "height": height,
            }
        }
        
        if seed:
            payload["parameters"]["seed"] = seed
        
        response = requests.post(self.url, headers=headers, json=payload, timeout=120)
        self.last_request_time = time.time()
        
        if response.status_code == 503:
            time.sleep(5)
            return self.generate_single(prompt, negative, width, height, steps, cfg, seed)
        
        if response.status_code != 200:
            raise Exception(f"HuggingFace API 调用失败: {response.text}")
        
        return Image.open(io.BytesIO(response.content))