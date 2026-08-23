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
        self.base_url = base_url or "https://openai.good.hidns.vip/v1"
        self.api_key = "https://github.com/smanx/free-api"
        
        # ✅ 只保留真正可用的图像模型
        self.available_models = ["grok-imagine-image-lite"]
        self.verified_models = ["grok-imagine-image-lite"]  # 已验证可用
        
        # 尝试获取更多模型，但只保留图像模型
        self._fetch_models()
        
        # ✅ 始终优先使用已验证的模型
        self.model = "grok-imagine-image-lite"
        if self.model not in self.available_models:
            self.available_models.insert(0, self.model)
        
        # 支持的尺寸
        self.supported_sizes = [
            "256x256", "512x512", "1024x1024",
            "1024x768", "768x1024",
            "1280x720", "720x1280",
        ]
        
        # 限速
        self.last_request_time = 0
        self.min_interval = 2.5
        
        # ✅ 最大重试次数
        self.MAX_RETRIES = 3
        self.retry_count = 0
        
        print(f"🔍 Free API 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 可用模型: {self.available_models}")
        print(f"🔍 当前模型: {self.model}")
        print(f"⚠️ 注意: Free API 有 IP 限流 (10秒5次)")
    
    def _fetch_models(self):
        """获取可用模型列表 - 只保留图像生成模型"""
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    all_models = [m.get('id', str(m)) for m in data['data']]
                    all_models = [m for m in all_models if m and m != '...']
                    
                    # ✅ 只保留 grok-imagine-image-lite（已验证可用）
                    verified = ["grok-imagine-image-lite"]
                    
                    # 过滤出已验证的模型
                    filtered = [m for m in all_models if m in verified]
                    
                    if filtered:
                        self.available_models = filtered
                        print(f"✅ 获取到 {len(self.available_models)} 个可用模型")
                    else:
                        # 如果没有找到，保留默认
                        if "grok-imagine-image-lite" not in self.available_models:
                            self.available_models = ["grok-imagine-image-lite"]
                        print(f"⚠️ 未找到可用模型，使用默认: {self.available_models}")
                else:
                    print(f"⚠️ 无法解析模型列表: {data}")
            else:
                print(f"⚠️ 获取模型列表失败: {response.status_code}")
        except Exception as e:
            print(f"⚠️ 获取模型列表异常: {e}")
        
        # 确保 grok-imagine-image-lite 在列表中
        if "grok-imagine-image-lite" not in self.available_models:
            self.available_models.insert(0, "grok-imagine-image-lite")
    
    def _select_best_model(self) -> str:
        """选择最佳可用模型 - 只使用已验证的模型"""
        verified = ["grok-imagine-image-lite"]
        for vm in verified:
            if vm in self.available_models:
                return vm
        return self.available_models[0] if self.available_models else "grok-imagine-image-lite"
    
    def _get_size(self, width: int, height: int) -> str:
        """获取支持的尺寸格式"""
        size = f"{width}x{height}"
        if size in self.supported_sizes:
            return size
        
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
        
        # ✅ 重置重试计数（每次新生成重置）
        self.retry_count = 0
        
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
        
        if not url.startswith(('http://', 'https://')):
            raise Exception(f"无效的 API URL: {url}")
        
        print(f"🔍 Free API 请求")
        print(f"🔍 模型: {self.model}, 尺寸: {size}")
        print(f"🔍 URL: {url}")
        
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
                
                # ✅ 检查是否是模型不可用错误（400 也是不可用）
                is_model_error = (
                    response.status_code in [502, 503, 504] or
                    (response.status_code == 400 and "model" in error_msg.lower())
                )
                
                if is_model_error:
                    self.retry_count += 1
                    
                    if self.retry_count > self.MAX_RETRIES:
                        raise Exception(
                            f"已尝试 {self.MAX_RETRIES} 次，模型 {self.model} 不可用。\n"
                            f"Free API 当前可能不可用，请：\n"
                            f"1. 切换到 Pollinations (API 下拉选择 pollinations)\n"
                            f"2. 稍后重试"
                        )
                    
                    print(f"⚠️ 模型 {self.model} 不可用 (尝试 {self.retry_count}/{self.MAX_RETRIES})")
                    
                    # ✅ 强制切换到 grok-imagine-image-lite（唯一可信模型）
                    if self.model != "grok-imagine-image-lite":
                        self.model = "grok-imagine-image-lite"
                        print(f"🔄 切换模型: {self.model}")
                    else:
                        # 如果 grok 也不行，说明 Free API 整体不可用
                        raise Exception(
                            f"模型 {self.model} 不可用，Free API 可能暂时离线。\n"
                            f"请切换到 Pollinations 或稍后重试。"
                        )
                    
                    # 递归重试
                    return self.generate_single(
                        prompt, negative, width, height, 
                        steps, cfg, seed
                    )
                
                if response.status_code == 429:
                    error_msg = f"请求过于频繁 (限流: 10秒5次)，请稍后重试。{error_msg}"
                
                raise Exception(f"Free API 调用失败 (状态码 {response.status_code}): {error_msg}")
            
            # ✅ 成功，重置重试计数
            self.retry_count = 0
            
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
            
        except requests.exceptions.MissingSchema as e:
            raise Exception(f"Free API URL 无效，请检查配置: {e}")
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

    def get_model(self) -> str:
        return self.model
    
    def get_name(self) -> str:
        return f"Free API ({self.model})"