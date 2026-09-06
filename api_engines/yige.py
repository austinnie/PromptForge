"""文心一格 API 图像生成引擎"""

import os
import base64
import requests
from PIL import Image
import io
import time
import random 

class YigeEngine:
    """文心一格 API 引擎"""
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires = 0
        
        # 文心一格支持的大小
        self.supported_sizes = {
            "512*512": "512x512",
            "768*768": "768x768",
            "1024*1024": "1024x1024",
        }
    
    def _get_access_token(self):
        """获取百度 access_token"""
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        
        response = requests.post(url, params=params, timeout=30)
        if response.status_code != 200:
            raise Exception(f"获取 access_token 失败: {response.text}")
        
        data = response.json()
        self.access_token = data.get("access_token")
        expires_in = data.get("expires_in", 2592000)  # 默认30天
        self.token_expires = time.time() + expires_in - 3600  # 提前1小时过期
        
        return self.access_token
    
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
    
        if not self.api_key or not self.secret_key:
            raise ValueError("请设置 YIGE_API_KEY 和 YIGE_SECRET_KEY")
        
        # 文心一格使用 768x768 默认
        size_key = f"{width}*{height}"
        resolution = self.supported_sizes.get(size_key, "1024x1024")
        
        # 获取 token
        access_token = self._get_access_token()
        
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/image_generation?access_token={access_token}"
        
        # 文心一格 v2 接口
        data = {
            "prompt": prompt,
            "negative_prompt": negative or "worst quality, low quality, ugly",
            "resolution": resolution,
            "num": 1,
            "style": "摄影",  # 可选: 动漫, 写实, 油画, 水彩, 摄影
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"文心一格 API 调用失败: {response.text}")
        
        result = response.json()
        
        if result.get("error_code"):
            raise Exception(f"文心一格错误: {result.get('error_msg')}")
        
        # 解析图片
        image_base64 = result.get("data", [{}])[0].get("image")
        if not image_base64:
            raise Exception("文心一格未返回图片")
        
        image_bytes = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(image_bytes))
    
    def get_usage(self):
        """获取使用量"""
        return {"info": "请登录百度智能云控制台查看使用量"}

    def get_name(self) -> str:
        return "文心一格"        