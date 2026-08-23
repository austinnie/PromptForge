"""Agnes AI 图像生成引擎 - 无限期免费，需注册获取 API Key"""

import os
import requests
from PIL import Image
import io
import json
import time
from typing import Optional


class AgnesEngine:
    """Agnes AI 图像生成引擎"""
    
    def __init__(self, api_key: str, model: str = "flux", base_url: str = None):
        """
        初始化 Agnes AI 引擎
        
        Args:
            api_key: Agnes AI API Key（从 https://www.agnes.ai 获取）
            model: 模型名称，可选: flux, sdxl, sd3, turbo
            base_url: API 地址
        """
        self.api_key = api_key
        self.model = model or "flux"
        self.base_url = base_url or "https://api.agnes.ai/v1"
        
        if not self.api_key:
            print("⚠️ 未设置 AGNES_API_KEY，请从 https://www.agnes.ai 注册获取")
        
        # 支持的模型
        self.available_models = ["flux", "sdxl", "sd3", "turbo", "qwen-image"]
        
        # 支持的尺寸
        self.supported_sizes = [
            "512x512", "768x768", "1024x1024",
            "1024x768", "768x1024",
            "1280x720", "720x1280",
        ]
        
        # 默认尺寸
        self.default_width = 1024
        self.default_height = 1024
        
        # 限速
        self.last_request_time = 0
        self.min_interval = 0.5
        
        print(f"🔍 Agnes AI 引擎初始化 (模型: {model})")
    
    def _get_size(self, width: int, height: int) -> str:
        """获取支持的尺寸"""
        size = f"{width}x{height}"
        if size in self.supported_sizes:
            return size
        
        # 找最接近的
        aspect = width / height
        best_match = "1024x1024"
        best_diff = float('inf')
        for s in self.supported_sizes:
            w, h = map(int, s.split('x'))
            diff = abs(aspect - w/h)
            if diff < best_diff:
                best_diff = diff
                best_match = s
        
        return best_match
    
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
        
        if not self.api_key:
            raise ValueError("请设置 AGNES_API_KEY")
        
        # 限速
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        # 获取尺寸
        size = self._get_size(width, height)
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Agnes AI 使用 OpenAI 兼容接口
        data = {
            "model": self.model,
            "prompt": prompt,
            "negative_prompt": negative,
            "size": size,
            "n": 1,
            "steps": steps,
            "guidance_scale": cfg,
        }
        
        if seed is not None:
            data["seed"] = seed
        
        url = f"{self.base_url}/images/generations"
        
        print(f"🔍 Agnes AI 请求: {url}")
        print(f"🔍 模型: {self.model}, 尺寸: {size}")
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=120
            )
            
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                error_detail = {}
                try:
                    error_detail = response.json()
                except:
                    pass
                
                if error_detail:
                    error_msg = error_detail.get('error', {}).get('message', str(error_detail))
                else:
                    error_msg = response.text[:200]
                
                raise Exception(f"Agnes AI API 调用失败 (状态码 {response.status_code}): {error_msg}")
            
            result = response.json()
            
            # 解析图片
            image_url = None
            
            # 格式: data[0].url (OpenAI 兼容)
            if 'data' in result and result['data']:
                image_url = result['data'][0].get('url')
            
            # 格式: output.results[0].url (其他格式)
            if not image_url and 'output' in result:
                output = result['output']
                if 'results' in output and output['results']:
                    image_url = output['results'][0].get('url')
                elif 'image_url' in output:
                    image_url = output['image_url']
            
            if not image_url:
                raise Exception(f"无法解析图片URL，响应: {json.dumps(result)[:300]}")
            
            # 下载图片
            if image_url.startswith("data:image"):
                import re
                base64_data = re.sub(r"^data:image/.+;base64,", "", image_url)
                image_bytes = base64.b64decode(base64_data)
                return Image.open(io.BytesIO(image_bytes))
            
            # HTTP URL
            img_response = requests.get(image_url, timeout=30)
            if img_response.status_code != 200:
                raise Exception(f"下载图片失败: {img_response.status_code}")
            return Image.open(io.BytesIO(img_response.content))
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Agnes AI 请求失败: {e}")
        except Exception as e:
            raise Exception(f"Agnes AI 生成失败: {e}")
    
    def get_usage(self):
        """获取使用量信息"""
        # Agnes AI 可能没有公开的用量查询 API
        return {"info": "请登录 Agnes AI 控制台查看使用量"}
    
    def get_name(self) -> str:
        return f"Agnes AI ({self.model})"


class AgnesImageToImageEngine:
    """Agnes AI 图生图引擎"""
    
    def __init__(self, api_key: str, model: str = "flux"):
        self.api_key = api_key
        self.model = model or "flux"
        self.base_url = "https://api.agnes.ai/v1"
    
    def generate(
        self,
        prompt: str,
        image: Image.Image,
        strength: float = 0.5,
        **kwargs
    ) -> Image.Image:
        """图生图"""
        
        if not self.api_key:
            raise ValueError("请设置 AGNES_API_KEY")
        
        # 将图片转为 base64
        import base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "image": f"data:image/png;base64,{image_base64}",
            "strength": strength,
            "n": 1,
        }
        
        url = f"{self.base_url}/images/edits"
        
        response = requests.post(url, headers=headers, json=data, timeout=120)
        
        if response.status_code != 200:
            raise Exception(f"Agnes AI 图生图失败: {response.text}")
        
        result = response.json()
        image_url = result.get('data', [{}])[0].get('url')
        
        if not image_url:
            raise Exception("无法获取图片")
        
        img_response = requests.get(image_url, timeout=30)
        return Image.open(io.BytesIO(img_response.content))