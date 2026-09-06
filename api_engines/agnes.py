# core/api_engines/agnes.py
"""
Agnes AI 图像生成引擎 - 无限期免费，需注册获取 API Key
支持：文生图、图生图、推理、视频生成
"""

import os
import requests
from PIL import Image
import io
import json
import time
import base64
from typing import Optional, Dict, Any, List
from enum import Enum


class AgnesMode(Enum):
    """Agnes AI 支持的模式"""
    TEXT_TO_IMAGE = "text-to-image"
    IMAGE_TO_IMAGE = "image-to-image"
    CHAT = "chat"           # 推理/对话
    VIDEO = "video"         # 视频生成


class AgnesEngine:
    """Agnes AI 多模态引擎"""
    
    # 默认模型映射
    DEFAULT_MODELS = {
        "text-to-image": "agnes-image-2.1-flash",
        "image-to-image": "agnes-image-2.1-flash",
        "chat": "agnes-text-2.1-flash",
        "video": "agnes-video-2.1-flash",
        "vision": "agnes-vision-2.1-flash",
    }
    
    def __init__(
        self,
        api_key: str,
        base_url: str = None,
        model: str = None,
        image_model: str = None,
        text_model: str = None,
        video_model: str = None,
        vision_model: str = None,
    ):
        """
        初始化 Agnes AI 引擎
        
        Args:
            api_key: Agnes AI API Key
            base_url: API 地址
            model: 默认模型（不指定时使用各能力默认模型）
            image_model: 图像生成模型
            text_model: 文本模型
            video_model: 视频模型
            vision_model: 视觉模型
        """
        self.api_key = api_key
        self.base_url = base_url or "https://apihub.agnes-ai.com/v1"
        
        # 各能力模型配置
        self.image_model = image_model or model or self.DEFAULT_MODELS["text-to-image"]
        self.text_model = text_model or model or self.DEFAULT_MODELS["chat"]
        self.video_model = video_model or model or self.DEFAULT_MODELS["video"]
        self.vision_model = vision_model or model or self.DEFAULT_MODELS["vision"]
        
        # 支持的尺寸
        self.supported_sizes = [
            "512x512", "768x768", "1024x1024",
            "1024x768", "768x1024",
            "1280x720", "720x1280",
        ]
        
        # 限速
        self.last_request_time = 0
        self.min_interval = 0.5
        
        if not self.api_key:
            print("⚠️ 未设置 AGNES_API_KEY，请从 https://apihub.agnes-ai.com 注册获取")
        
        print(f"🔍 Agnes AI 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 图像模型: {self.image_model}")
        print(f"🔍 文本模型: {self.text_model}")
        print(f"🔍 视频模型: {self.video_model}")
    
    def _get_size(self, width: int, height: int) -> str:
        """获取支持的尺寸"""
        size = f"{width}x{height}"
        if size in self.supported_sizes:
            return size
        
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
    
    def _request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """发送请求到 Agnes AI API"""
        if not self.api_key:
            raise ValueError("请设置 AGNES_API_KEY")
        
        # 限速
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=timeout
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
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Agnes AI 请求失败: {e}")
    
    def _download_image(self, image_url: str) -> Image.Image:
        """下载图片"""
        if image_url.startswith("data:image"):
            import re
            base64_data = re.sub(r"^data:image/.+;base64,", "", image_url)
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes))
        
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            raise Exception(f"下载图片失败: {img_response.status_code}")
        return Image.open(io.BytesIO(img_response.content))
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """将 PIL Image 转为 base64"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    # ==================== 文生图 ====================
    
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
        """生成单张图片（文生图）"""
        return self.text_to_image(prompt, negative, width, height, steps, cfg, seed)
    
    def text_to_image(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """文生图"""
        size = self._get_size(width, height)
        
        data = {
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "url",
        }
        
        #if negative:
        #    data["negative_prompt"] = negative
        
        if seed is not None:
            data["seed"] = seed
        #if steps:
        #    data["steps"] = steps
        #if cfg:
        #    data["guidance_scale"] = cfg
        
        print(f"🔍 Agnes AI 文生图")
        print(f"🔍 模型: {self.image_model}, 尺寸: {size}")
        
        result = self._request("images/generations", data)
        
        # 解析图片
        image_url = None
        if 'data' in result and result['data']:
            image_url = result['data'][0].get('url')
        
        if not image_url and 'output' in result:
            output = result['output']
            if 'results' in output and output['results']:
                image_url = output['results'][0].get('url')
            elif 'image_url' in output:
                image_url = output['image_url']
        
        if not image_url:
            raise Exception(f"无法解析图片URL，响应: {json.dumps(result)[:300]}")
        
        return self._download_image(image_url)
    
    # ==================== 图生图 ====================
    
    def image_to_image(
        self,
        prompt: str,
        image: Image.Image,
        strength: float = 0.7,   # 保留但不使用
        width: int = None,
        height: int = None,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """
        图生图 - 使用 multipart/form-data 上传
        """
        # 获取尺寸（用于显示）
        if width is None or height is None:
            width, height = image.size
        size = f"{width}x{height}"

        # 将图片转为 bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # 构建 multipart 数据
        data = {
            "model": self.image_model,
            "prompt": prompt,
            "n": "1",
            "size": size,
            "response_format": "url",
        }
        # ⭐ 不发送 strength, steps, cfg, seed（这些参数可能不支持）

        files = {
            "image": ("image.png", img_bytes, "image/png")
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            # 不设置 Content-Type，让 requests 自动处理 multipart
        }

        url = f"{self.base_url}/images/edits"

        print(f"🔍 Agnes AI 图生图 (multipart)")
        print(f"🔍 模型: {self.image_model}, 尺寸: {size}")

        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=120
            )

            if response.status_code != 200:
                error_detail = {}
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get('error', {}).get('message', str(error_detail))
                except:
                    error_msg = response.text[:200]
                raise Exception(f"Agnes AI API 调用失败 (状态码 {response.status_code}): {error_msg}")

            result = response.json()

            # 解析图片 URL
            image_url = None
            if 'data' in result and result['data']:
                image_url = result['data'][0].get('url')
            if not image_url:
                raise Exception(f"无法解析图片URL，响应: {json.dumps(result)[:300]}")

            return self._download_image(image_url)

        except requests.exceptions.RequestException as e:
            raise Exception(f"Agnes AI 请求失败: {e}")
        
    # ==================== 推理/对话 ====================
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """
        推理/对话
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称（默认使用 text_model）
            temperature: 温度参数
            max_tokens: 最大 token 数
            stream: 是否流式输出
        
        Returns:
            模型响应文本
        """
        model = model or self.text_model
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        
        print(f"🔍 Agnes AI 推理/对话")
        print(f"🔍 模型: {model}")
        
        if stream:
            # 流式响应
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=data,
                stream=True,
                timeout=120
            )
            
            if response.status_code != 200:
                raise Exception(f"Agnes AI 推理失败: {response.text}")
            
            result_text = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        line = line[6:]
                        if line == '[DONE]':
                            break
                        try:
                            chunk = json.loads(line)
                            if 'choices' in chunk and chunk['choices']:
                                delta = chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    print(content, end='', flush=True)
                                    result_text += content
                        except:
                            pass
            
            print()  # 换行
            return result_text
        
        # 非流式
        result = self._request("chat/completions", data)
        
        if 'choices' in result and result['choices']:
            return result['choices'][0].get('message', {}).get('content', '')
        
        raise Exception(f"无法解析推理结果: {json.dumps(result)[:300]}")
    
    def chat_simple(self, prompt: str, system_prompt: str = None) -> str:
        """简化版推理"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages)
    
    # ==================== 视频生成 ====================
    
    def video_generation(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        duration: int = 5,
        width: int = 768,
        height: int = 768,
        model: str = None,
        callback_url: str = None,
    ) -> Dict[str, Any]:
        """
        视频生成（可能为异步任务，返回任务ID）
        
        Args:
            prompt: 提示词
            image: 参考图（图生视频，可选）
            duration: 视频时长（秒）
            width: 视频宽度
            height: 视频高度
            model: 模型名称
            callback_url: 回调地址（可选）
        
        Returns:
            任务信息（包含 task_id）
        """
        model = model or self.video_model
        
        data = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "width": width,
            "height": height,
        }
        
        if image:
            data["image"] = f"data:image/png;base64,{self._image_to_base64(image)}"
        
        if callback_url:
            data["callback_url"] = callback_url
        
        print(f"🔍 Agnes AI 视频生成")
        print(f"🔍 模型: {model}, 时长: {duration}s, 尺寸: {width}x{height}")
        
        # 注意：视频生成可能需要异步处理，实际端点可能不同
        # 这里使用 images/generations 的变体，实际可能需要调整
        # 尝试不同的端点
        endpoints = ["videos/generations", "video/generations", "generations/video", "video"]
        for endpoint in endpoints:
            try:
                result = self._request(endpoint, data, timeout=300)
                # 如果成功则返回
                return result
            except Exception as e:
                if "404" in str(e):
                    continue
                raise
        raise Exception("所有视频端点均不可用")
    
    def video_status(self, task_id: str) -> Dict[str, Any]:
        """查询视频生成状态"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/videos/status/{task_id}"
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"查询视频状态失败: {response.text}")
        
        return response.json()
    
    def wait_for_video(self, task_id: str, max_wait: int = 300) -> str:
        """
        等待视频生成完成
        
        Args:
            task_id: 任务ID
            max_wait: 最大等待时间（秒）
        
        Returns:
            视频URL
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.video_status(task_id)
            state = status.get('state', '')
            
            if state == 'completed':
                return status.get('video_url', '')
            elif state == 'failed':
                raise Exception(f"视频生成失败: {status.get('error', '未知错误')}")
            
            print(f"⏳ 视频生成中... ({state})")
            time.sleep(5)
        
        raise Exception(f"视频生成超时 ({max_wait}s)")
    
    # ==================== 图片反推 ====================
    
    def image_to_text(
        self,
        image: Image.Image,
        prompt: str = "请描述这张图片的内容",
        model: str = None,
    ) -> str:
        """
        图片反推（多模态理解）
        
        Args:
            image: 图片
            prompt: 提示词（默认：请描述这张图片的内容）
            model: 模型名称（默认使用 vision_model）
        
        Returns:
            图片描述文本
        """
        model = model or self.vision_model
        
        image_base64 = self._image_to_base64(image)
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            }
        ]
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.7,
        }
        
        print(f"🔍 Agnes AI 图片反推")
        print(f"🔍 模型: {model}")
        
        result = self._request("chat/completions", data)
        
        if 'choices' in result and result['choices']:
            return result['choices'][0].get('message', {}).get('content', '')
        
        raise Exception(f"无法解析图片反推结果: {json.dumps(result)[:300]}")
    
    # ==================== 工具方法 ====================
    
    def get_usage(self) -> Dict[str, Any]:
        """获取使用量信息"""
        # Agnes AI 可能没有公开的用量查询 API
        return {"info": "请登录 Agnes AI 控制台查看使用量"}
    
    def get_name(self) -> str:
        return f"Agnes AI (图像: {self.image_model}, 文本: {self.text_model})"
    
    def get_model(self) -> str:
        return self.image_model