"""Free API 图像生成引擎 - 社区免费代理，无需注册"""

import os
import requests
from PIL import Image
import io
import time
import json
import base64
from typing import Optional, List


class FreeAPIEngine:
    """Free API 图像生成引擎 (社区免费代理)"""
    
    def __init__(self, model: str = "flux", base_url: str = None):
        """
        初始化 Free API 引擎
        
        Args:
            model: 模型名称，会自动检测可用模型
            base_url: API 地址
        """
        self.base_url = base_url or "https://openai.good.hidns.vip/v1"
        self.api_key = "https://github.com/smanx/free-api"
        
        # 可用模型列表（自动获取）
        self.available_models = []
        self._fetch_models()
        
        # 设置模型
        if model in self.available_models:
            self.model = model
        elif self.available_models:
            # 选择第一个可用的图像生成模型
            self.model = self._select_best_model()
        else:
            self.model = "flux"  # 默认
        
        # 支持的尺寸
        self.supported_sizes = [
            "256x256", "512x512", "1024x1024",
            "1024x768", "768x1024",
            "1280x720", "720x1280",
        ]
        
        # 限速
        self.last_request_time = 0
        self.min_interval = 2.5
        
        print(f"🔍 Free API 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 可用模型: {self.available_models}")
        print(f"🔍 当前模型: {self.model}")
        print(f"⚠️ 注意: Free API 有 IP 限流 (10秒5次)")
    
    def _fetch_models(self):
        """获取可用模型列表"""
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    # 过滤出图像生成模型
                    all_models = [m['id'] for m in data['data']]
                    # 常见的图像生成模型关键词
                    image_keywords = ['image', 'flux', 'sdxl', 'sd3', 'dall-e', 'qwen', 'wan']
                    self.available_models = [
                        m for m in all_models 
                        if any(kw in m.lower() for kw in image_keywords)
                    ]
                    # 如果没有匹配到，使用所有模型
                    if not self.available_models:
                        self.available_models = all_models
                    print(f"✅ 获取到 {len(self.available_models)} 个可用模型")
                else:
                    print(f"⚠️ 无法解析模型列表: {data}")
                    self.available_models = []
            else:
                print(f"⚠️ 获取模型列表失败: {response.status_code}")
                self.available_models = []
        except Exception as e:
            print(f"⚠️ 获取模型列表异常: {e}")
            self.available_models = []
        
        # 如果获取失败，使用默认列表
        if not self.available_models:
            self.available_models = ["flux", "sdxl", "sd3", "dall-e-3"]
            print(f"⚠️ 使用默认模型列表: {self.available_models}")
    
    def _select_best_model(self) -> str:
        """选择最佳可用模型"""
        # 按优先级排序
        priority = ["flux", "sdxl", "sd3", "dall-e-3", "qwen", "wan"]
        
        for p in priority:
            for m in self.available_models:
                if p in m.lower():
                    return m
        
        return self.available_models[0] if self.available_models else "flux"
    
    def _get_size(self, width: int, height: int) -> str:
        """获取支持的尺寸格式"""
        size = f"{width}x{height}"
        if size in self.supported_sizes:
            return size
        
        # 找最接近的
        aspect = width / height
        best_match = "1024x1024"
        best_diff = float('inf')
        
        for s in self.supported_sizes:
            w, h = map(int, s.split('x'))
            key_aspect = w / h
            diff = abs(aspect - key_aspect)
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
        
        # 限速
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        size = self._get_size(width, height)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        
        if negative:
            data["negative_prompt"] = negative
        if seed is not None:
            data["seed"] = seed
        if steps:
            data["steps"] = steps
        if cfg:
            data["guidance_scale"] = cfg
        
        url = f"{self.base_url}/images/generations"
        
        print(f"🔍 Free API 请求")
        print(f"🔍 模型: {self.model}, 尺寸: {size}")
        print(f"🔍 Prompt 长度: {len(prompt)}")
        
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
                    error_msg = error_detail.get('error', {}).get('message', str(error_detail))
                except:
                    error_msg = response.text[:200]
                
                # 如果是模型不可用错误，尝试切换模型
                if "no access to model" in error_msg or "model" in error_msg.lower():
                    print(f"⚠️ 模型 {self.model} 不可用，尝试切换...")
                    self._fetch_models()
                    if self.available_models:
                        old_model = self.model
                        self.model = self._select_best_model()
                        if self.model != old_model:
                            print(f"🔄 切换模型: {old_model} → {self.model}")
                            # 递归重试
                            return self.generate_single(
                                prompt, negative, width, height, 
                                steps, cfg, seed
                            )
                
                if response.status_code == 429:
                    error_msg = f"请求过于频繁 (限流: 10秒5次)，请稍后重试。{error_msg}"
                
                raise Exception(f"Free API 调用失败 (状态码 {response.status_code}): {error_msg}")
            
            result = response.json()
            
            # 解析图片
            image_data = None
            
            if 'data' in result and result['data']:
                item = result['data'][0]
                if 'b64_json' in item:
                    image_data = item['b64_json']
                elif 'url' in item:
                    img_response = requests.get(item['url'], timeout=30)
                    return Image.open(io.BytesIO(img_response.content))
                elif 'image' in item:
                    image_data = item['image']
            
            if not image_data:
                raise Exception(f"无法解析图片数据，响应: {json.dumps(result)[:300]}")
            
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                return Image.open(io.BytesIO(image_bytes))
            
            if isinstance(image_data, str) and image_data.startswith('http'):
                img_response = requests.get(image_data, timeout=30)
                return Image.open(io.BytesIO(img_response.content))
            
            raise Exception(f"无法解析图片数据: {type(image_data)}")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Free API 请求失败: {e}")
        except Exception as e:
            raise Exception(f"Free API 生成失败: {e}")
    
    def get_usage(self):
        return {
            "info": "Free API 是社区免费代理，无需注册",
            "model": self.model,
            "available_models": self.available_models,
            "limits": {"rate_limit": "10次/10秒"}
        }
    
    def get_name(self) -> str:
        return f"Free API ({self.model})"