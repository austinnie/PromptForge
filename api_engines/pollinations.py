"""Pollinations AI 图像生成引擎 - GET 方式"""

import os
import requests
from PIL import Image
import io
import time
import json
from typing import Optional
import urllib.parse


class PollinationsEngine:
    """Pollinations AI 图像生成引擎"""
    
    def __init__(self, model: str = "flux", base_url: str = None):
        self.model = model or "flux"
        self.base_url = "https://image.pollinations.ai/prompt/"
        self.available_models = ["flux", "turbo", "sdxl", "sd3", "qwen"]
        
        # 需要清理的质量词
        self.quality_words = [
            "masterpiece", "best quality", "photorealistic", "8k", 
            "highly detailed", "intricate details", "professional photography",
            "beautiful", "stunning", "amazing", "perfect", "gorgeous",
            "elegant", "high quality", "ultra detailed", "hdr",
            "highest quality", "sharp focus", "cinematic", "award winning"
        ]
        
        print(f"🔍 Pollinations AI 引擎初始化 (模型: {model})")
    
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
        
        # ============================================================
        # 步骤1：清理质量词
        # ============================================================
        clean_prompt = prompt
        for word in self.quality_words:
            clean_prompt = clean_prompt.replace(word, "")
            clean_prompt = clean_prompt.replace(word.title(), "")
        
        clean_prompt = ", ".join([p.strip() for p in clean_prompt.split(",") if p.strip()])
        if not clean_prompt:
            clean_prompt = prompt
        
        print(f"🔍 清理后 Prompt: {clean_prompt[:150]}...")
        
        # ============================================================
        # 步骤2：中文转英文
        # ============================================================
        english_prompt = self._to_english_prompt(clean_prompt)
        
        # ============================================================
        # 步骤3：限制长度（URL 安全）
        # ============================================================
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
        
        # ============================================================
        # 步骤4：构建请求
        # ============================================================
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
        
        # ✅ 核心参数（不包含 negative）
        params = {
            "width": width,
            "height": height,
            "model": self.model,
        }
        
        if seed is not None:
            params["seed"] = seed
        
        # ✅ 可选：只传极简的 negative（不超过 20 字符）
        # Pollinations 自带过滤，不传也没问题
        if negative and len(negative) < 50:
            params["negative"] = negative
        
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{param_str}"
        
        # URL 安全检查（防止过长）
        if len(full_url) > 1500:
            print(f"⚠️ URL 过长 ({len(full_url)} 字符)，自动精简")
            # 移除 negative 参数
            params.pop("negative", None)
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
            print(f"🔍 精简后 URL 长度: {len(full_url)}")
        
        print(f"🔍 Pollinations GET 请求")
        print(f"🔍 URL 长度: {len(full_url)}")
        print(f"🔍 模型: {self.model}, 尺寸: {width}x{height}")
        
        try:
            response = requests.get(
                full_url,
                timeout=120,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text[:300]
                print(f"🔍 错误响应: {error_text}")
                raise Exception(f"API 调用失败 (状态码 {response.status_code}): {error_text}")
            
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                try:
                    error_data = response.json()
                    raise Exception(f"API 错误: {error_data}")
                except:
                    pass
                raise Exception(f"响应不是图片: {content_type}")
            
            image = Image.open(io.BytesIO(response.content))
            
            if image.size[0] < 10 or image.size[1] < 10:
                raise Exception("生成的图片尺寸异常")
            
            return image
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Pollinations 请求失败: {e}")
        except Exception as e:
            raise Exception(f"Pollinations 生成失败: {e}")
    
    def _to_english_prompt(self, prompt: str) -> str:
        """将中文 Prompt 转换为英文"""
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
    
    def get_usage(self):
        return {"info": "Pollinations AI 完全免费，无使用限制"}

    def get_model(self) -> str:
        """获取当前使用的模型名称"""
        return self.model
    
    def get_name(self) -> str:
        return f"Pollinations AI ({self.model})"