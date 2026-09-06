"""Free API 图像生成引擎 - 社区免费代理，无需注册"""

import os
import requests
from PIL import Image
import io
import time
import json
import base64
from typing import Optional, List
import random


class FreeAPIEngine:
    """Free API 图像生成引擎 (社区免费代理)"""
    
    def __init__(self, model: str = "grok-imagine-image-lite", base_url: str = None):
        self.base_url = base_url or "https://openai.good.hidns.vip/v1"
        self.api_key = "https://github.com/smanx/free-api"
        
        # ✅ 使用传入的 model（命令行或 config 指定的）
        self.model = model
        
        # 可用模型列表
        self.available_models = [
            "grok-imagine-image-lite",
            "qwen3.7-plus",
            "flux",
            "zimage",
            "gptimage"
        ]
        
        # 确保传入的模型在列表中
        if self.model not in self.available_models:
            self.available_models.insert(0, self.model)
        
        # 尝试获取更多可用模型
        self._fetch_models()
        
        # ⭐ 关键修复：不再覆盖 self.model，保留用户传入的模型
        
        # 支持的尺寸
        self.supported_sizes = [
            "256x256", "512x512", "1024x1024",
            "1024x768", "768x1024",
            "1280x720", "720x1280",
        ]
        
        # 限速
        self.last_request_time = 0
        self.min_interval = 2.5
        
        # 最大重试次数
        self.MAX_RETRIES = 3
        self.retry_count = 0
        
        print(f"🔍 Free API 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 可用模型: {self.available_models}")
        print(f"🔍 当前模型: {self.model}")
        print(f"⚠️ 注意: Free API 有 IP 限流 (10秒5次)")
    
    def _fetch_models(self):
        """获取可用模型列表，保留传入的模型"""
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    all_models = [m.get('id', str(m)) for m in data['data']]
                    all_models = [m for m in all_models if m and m != '...']
                    
                    # ✅ 保留传入的模型
                    if self.model not in all_models:
                        all_models.append(self.model)
                    
                    self.available_models = all_models
                    print(f"✅ 获取到 {len(self.available_models)} 个可用模型")
                else:
                    print(f"⚠️ 无法解析模型列表: {data}")
            else:
                print(f"⚠️ 获取模型列表失败: {response.status_code}")
        except Exception as e:
            print(f"⚠️ 获取模型列表异常: {e}")
        
        # 确保一些常用图像模型在列表中（但不覆盖用户指定的）
        default_models = ["grok-imagine-image-lite", "qwen3.7-plus", "flux"]
        for m in default_models:
            if m not in self.available_models:
                self.available_models.append(m)
    
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

        if seed is None:
            seed = random.randint(1, 2**32 - 1)

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

        # ✅ 重试循环（不使用递归）
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            print(f"🔍 Free API 请求 (尝试 {attempt}/{max_retries})")
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

                if response.status_code == 200:
                    # 成功，解析图片
                    result = response.json()
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

                else:
                    # 非 200 状态码
                    error_detail = {}
                    try:
                        error_detail = response.json()
                        error_msg = error_detail.get('error', {}).get('message', str(error_detail))
                    except:
                        error_msg = response.text[:200]

                    # 检查是否是模型不可用错误
                    is_model_error = (
                        response.status_code in [502, 503, 504] or
                        (response.status_code == 400 and "model" in error_msg.lower())
                    )

                    if is_model_error:
                        print(f"⚠️ 模型 {self.model} 不可用 (尝试 {attempt}/{max_retries})")
                        if attempt == max_retries:
                            raise Exception(
                                f"已尝试 {max_retries} 次，模型 {self.model} 不可用。\n"
                                f"Free API 当前可能不可用，请：\n"
                                f"1. 切换到 Pollinations (--api pollinations)\n"
                                f"2. 使用其他模型 (--freeapi-model 模型名)\n"
                                f"3. 稍后重试"
                            )
                        # 等待后继续循环
                        time.sleep(2)
                        continue
                    else:
                        # 其他错误，直接抛出
                        raise Exception(f"Free API 调用失败 (状态码 {response.status_code}): {error_msg}")

            except requests.exceptions.RequestException as e:
                print(f"⚠️ 请求异常 (尝试 {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise Exception(f"Free API 请求失败: {e}")
                time.sleep(2)
                continue
            except Exception as e:
                # 其他异常直接抛出
                raise

        # 如果循环结束仍未返回，抛出异常
        raise Exception("Free API 生成失败：所有重试已用尽")
    
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