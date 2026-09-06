# core/api_engines/pollinations.py

import os
import requests
from PIL import Image
import io
import time
import json
import random
import urllib.parse
from typing import Optional


class PollinationsEngine:
    """Pollinations AI 图像生成引擎 - GET 方式"""
    
    def __init__(self, model: str = None, base_url: str = None):
        self.base_url = "https://image.pollinations.ai/prompt/"
        self.models_api_url = "https://image.pollinations.ai/models"
        
        # 硬编码备选模型列表（API 获取失败时使用）
        self.fallback_models = ["flux", "turbo", "sdxl", "sd3", "qwen"]
        
        # ⭐ 获取可用模型列表
        self.available_models = self._fetch_models()
        
        # ⭐ 确定使用的模型
        # 优先级：用户指定 > 可用列表第一个 > 备选列表第一个
        if model and model in self.available_models:
            self.model = model
        elif model and model in self.fallback_models:
            # 用户指定的模型不在可用列表中，但可能是有效的，尝试使用
            self.model = model
        elif self.available_models:
            self.model = self.available_models[0]
        else:
            self.model = "flux"
        
        # 质量词列表
        self.quality_words = [
            "masterpiece", "best quality", "photorealistic", "8k", 
            "highly detailed", "intricate details", "professional photography",
            "beautiful", "stunning", "amazing", "perfect", "gorgeous",
            "elegant", "high quality", "ultra detailed", "hdr",
            "highest quality", "sharp focus", "cinematic", "award winning"
        ]
        
        print(f"🔍 Pollinations AI 引擎初始化")
        print(f"🔍 可用模型: {self.available_models}")
        print(f"🔍 当前模型: {self.model}")
    
    def _fetch_models(self) -> list:
        """
        从 Pollinations API 获取可用模型列表
        如果 API 返回不完整，使用已知模型列表补全
        """
        # 经过验证的 Pollinations 模型列表
        KNOWN_MODELS = ["flux", "turbo", "sdxl", "sd3", "qwen", "sana"]
        
        api_models = []
        try:
            response = requests.get(self.models_api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    api_models = data
                elif isinstance(data, dict) and 'models' in data:
                    api_models = data['models']
        except Exception as e:
            print(f"⚠️ 获取模型列表失败: {e}")
        
        # 合并 API 返回 + 已知模型（去重并排序）
        all_models = list(set(api_models + KNOWN_MODELS))
        all_models = [m for m in all_models if m and isinstance(m, str)]
        all_models.sort()  # 排序使输出更稳定
        
        if all_models:
            print(f"✅ 可用模型: {', '.join(all_models)}")
            return all_models
        
        print(f"⚠️ 使用备选模型列表: {KNOWN_MODELS}")
        return KNOWN_MODELS
    
    def _to_english_prompt(self, prompt: str) -> str:
        """将中文 Prompt 转换为英文"""
        # ... 保持原有翻译逻辑不变 ...
        if all(ord(c) < 128 for c in prompt):
            return prompt
        
        translations = {
            "日落": "sunset", "日出": "sunrise",
            "风景": "landscape", "山水": "mountain and water",
            "水墨画": "ink wash painting", "国画": "traditional Chinese painting",
            "风格": "style", "自然": "nature", "景观": "scenery",
            "美女": "beautiful woman", "女孩": "girl", "男孩": "boy",
            "男人": "man", "女人": "woman",
            "动漫": "anime", "赛博朋克": "cyberpunk",
            "城市": "city", "森林": "forest", "海洋": "ocean",
            "沙滩": "beach", "星空": "starry sky",
            "唯美": "aesthetic", "写实": "photorealistic",
            "肖像": "portrait", "全身": "full body", "半身": "half body",
            "侧面": "side view", "正面": "front view",
            "温暖": "warm", "冷色": "cold color",
            "金色": "golden", "蓝色": "blue", "红色": "red",
            "粉色": "pink", "浪漫": "romantic",
            "梦幻": "dreamy", "复古": "vintage", "未来": "futuristic",
        }
        
        result = prompt
        for cn, en in translations.items():
            result = result.replace(cn, en)
        
        return result
    
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
        """生成单张图片 - 使用 GET 请求"""
        
        # 限制 seed 范围
        if seed is None:
            seed = random.randint(1, 2**31 - 1)
        else:
            seed = int(seed) & 0x7fffffff
        
        # 清理质量词
        clean_prompt = prompt
        for word in self.quality_words:
            clean_prompt = clean_prompt.replace(word, "")
            clean_prompt = clean_prompt.replace(word.title(), "")
        
        clean_prompt = ", ".join([p.strip() for p in clean_prompt.split(",") if p.strip()])
        if not clean_prompt:
            clean_prompt = prompt
        
        print(f"🔍 清理后 Prompt: {clean_prompt[:150]}...")
        
        # 中文转英文
        english_prompt = self._to_english_prompt(clean_prompt)
        
        # 限制长度
        max_length = 300
        if len(english_prompt) > max_length:
            parts = english_prompt.split(",")
            truncated = ""
            for part in parts:
                if len(truncated) + len(part) < max_length:
                    truncated += part + ", "
                else:
                    break
            english_prompt = truncated.rstrip(", ")
        if len(english_prompt) > max_length:
            english_prompt = english_prompt[:max_length]
        
        print(f"🔍 最终 Prompt: {english_prompt[:150]}...")
        print(f"🔍 最终长度: {len(english_prompt)}")
        
        # 构建 URL
        encoded_prompt = urllib.parse.quote(english_prompt)
        
        # 限制尺寸
        if width > 1024:
            scale = 1024 / width
            width = 1024
            height = int(height * scale)
        if height > 1024:
            scale = 1024 / height
            height = 1024
            width = int(width * scale)
        
        width = int(width)
        height = int(height)
        
        url = f"{self.base_url}{encoded_prompt}"
        
        # 核心参数
        params = {
            "width": width,
            "height": height,
            "model": self.model,
            "seed": seed,
        }

        # ✅ 添加可选参数
        if cfg:
            params["cfg"] = cfg
        if steps:
            params["steps"] = steps
    
        if negative and len(negative) < 50:
            params["negative"] = negative
        
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{param_str}"
        
        # URL 过长时移除 negative
        if len(full_url) > 1500:
            params.pop("negative", None)
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
        
        print(f"🔍 Pollinations GET 请求")
        print(f"🔍 URL 长度: {len(full_url)}")
        print(f"🔍 模型: {self.model}, 尺寸: {width}x{height}")
        
        # 重试逻辑
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    full_url,
                    timeout=120,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                if response.status_code == 200:
                    image = Image.open(io.BytesIO(response.content))
                    if image.size[0] < 10 or image.size[1] < 10:
                        raise Exception("生成的图片尺寸异常")
                    return image
                
                # 400/500 错误，重试时移除 seed
                if response.status_code in [400, 500] and attempt == 0:
                    print(f"⚠️ 请求失败 (状态码 {response.status_code})，重试（移除 seed）...")
                    params.pop("seed", None)
                    param_str = "&".join([f"{k}={v}" for k, v in params.items()])
                    full_url = f"{url}?{param_str}"
                    continue
                
                # 其他错误
                error_text = response.text[:300]
                print(f"🔍 错误响应: {error_text}")
                raise Exception(f"API 调用失败 (状态码 {response.status_code}): {error_text}")
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Pollinations 请求失败: {e}")
                print(f"⚠️ 请求异常 (尝试 {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                print(f"⚠️ 生成异常 (尝试 {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
        
        raise Exception("Pollinations 生成失败：所有重试已用尽")
    
    def get_usage(self):
        return {"info": "Pollinations AI 完全免费，无使用限制"}

    def get_model(self) -> str:
        return self.model
    
    def get_name(self) -> str:
        return f"Pollinations AI ({self.model})"