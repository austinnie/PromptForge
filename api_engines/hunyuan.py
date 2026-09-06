"""腾讯混元 API 图像生成引擎"""

import os
from PIL import Image
import base64
import io

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
except ImportError:
    credential = None
    hunyuan_client = None
    models = None

import random 

class HunyuanEngine:
    """腾讯混元 API 引擎"""
    
    def __init__(self, secret_id: str, secret_key: str):
        self.secret_id = secret_id
        self.secret_key = secret_key
        
        if not credential:
            raise ImportError("请安装 tencentcloud-sdk-python: pip install tencentcloud-sdk-python")
    
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
    
        if not self.secret_id or not self.secret_key:
            raise ValueError("请设置 HUNYUAN_SECRET_ID 和 HUNYUAN_SECRET_KEY")
        
        # 腾讯混元的图片生成 API 是文生图
        # 注意：腾讯混元目前主要通过控制台或 API 调用
        
        try:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "hunyuan.tencentcloudapi.com"
            
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            
            client = hunyuan_client.HunyuanClient(cred, "", client_profile)
            
            req = models.TextToImageRequest()
            req.Prompt = prompt
            req.NegativePrompt = negative or "worst quality, low quality"
            req.Width = width
            req.Height = height
            
            if seed:
                req.Seed = seed
            
            resp = client.TextToImage(req)
            
            # 解析返回的图片
            image_base64 = resp.ImageBase64
            if not image_base64:
                raise Exception("腾讯混元未返回图片")
            
            image_bytes = base64.b64decode(image_base64)
            return Image.open(io.BytesIO(image_bytes))
            
        except Exception as e:
            raise Exception(f"腾讯混元 API 调用失败: {e}")
    
    def get_usage(self):
        """获取使用量"""
        return {"info": "请登录腾讯云控制台查看使用量"}

    def get_name(self) -> str:
        return "腾讯混元"        