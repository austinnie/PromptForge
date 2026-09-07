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
    
    # ✅ 根据官方文档更新模型名称
    DEFAULT_MODELS = {
        "text-to-image": "agnes-image-2.1-flash",  # ✅ 官方文档确认
        "image-to-image": "agnes-image-2.1-flash", # ✅ 官方文档确认
        "chat": "agnes-2.5-flash",                 # ✅ 官方文档：agnes-2.5-flash
        "video": "agnes-video-v2.0",               # ✅ 官方文档：agnes-video-v2.0
        "vision": "agnes-2.5-flash",               # ✅ 官方文档：agnes-2.5-flash 支持视觉
    }
    
    # ✅ Agnes 官方服务路由（按优先级排序）
    ROUTES = [
        "https://apihub.agnes-ai.com/v1",   # 国际服务（主）
        "https://apihub.agnes-ai.cn/v1",    # 国际服务（备用）
        "https://api.agnes-ai.cn/v1",       # 中国服务
    ]
    
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
            base_url: API 地址（如果不指定，将使用主路由）
            model: 默认模型（不指定时使用各能力默认模型）
            image_model: 图像生成模型
            text_model: 文本模型
            video_model: 视频模型
            vision_model: 视觉模型
        """
        self.api_key = api_key
        
        # ✅ 设置基础 URL
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = self.ROUTES[0]  # 默认主路由
        
        # ✅ 记录当前使用的路由索引
        self._current_route_index = 0
        self._failed_routes = set()
        
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
        
        # ✅ 重试配置
        self.max_retries = 3
        self.retry_delay = 2
        
        if not self.api_key:
            print("⚠️ 未设置 AGNES_API_KEY，请从 https://platform.agnes-ai.com/ 注册获取")
        
        print(f"🔍 Agnes AI 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 备用路由: {self.ROUTES[1:]}")
        print(f"🔍 图像模型: {self.image_model}")
        print(f"🔍 文本模型: {self.text_model}")
        print(f"🔍 视频模型: {self.video_model}")
    
    def _get_working_route(self) -> str:
        """获取可用的路由"""
        # 如果有当前路由且未失败，直接使用
        if self._current_route_index < len(self.ROUTES):
            route = self.ROUTES[self._current_route_index]
            if route not in self._failed_routes:
                return route
        
        # 尝试其他路由
        for i, route in enumerate(self.ROUTES):
            if route not in self._failed_routes:
                self._current_route_index = i
                self.base_url = route
                print(f"🔄 切换到备用路由: {route}")
                return route
        
        # 所有路由都失败，重置并返回第一个
        print("⚠️ 所有路由均不可用，重置路由列表...")
        self._failed_routes.clear()
        self._current_route_index = 0
        self.base_url = self.ROUTES[0]
        return self.ROUTES[0]
    
    def _mark_route_failed(self, route: str):
        """标记路由为失败"""
        self._failed_routes.add(route)
        print(f"⚠️ 路由 {route} 已标记为不可用")
    
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
        """发送请求到 Agnes AI API（带路由切换）"""
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
        
        # ✅ 尝试多个路由
        max_attempts = len(self.ROUTES) * 2
        for attempt in range(max_attempts):
            route = self._get_working_route()
            url = f"{route}/{endpoint.lstrip('/')}"
            
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=timeout
                )
                
                self.last_request_time = time.time()
                
                # ✅ 503 错误 - 服务不可用，切换路由
                if response.status_code == 503:
                    print(f"⚠️ 路由 {route} 返回 503，尝试切换...")
                    self._mark_route_failed(route)
                    time.sleep(1)
                    continue
                
                # ✅ 429 错误 - 限流，等待后重试
                if response.status_code == 429:
                    print(f"⚠️ 请求限流 (429)，等待后重试...")
                    time.sleep(3)
                    continue
                
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
                
            except requests.exceptions.ConnectionError:
                print(f"⚠️ 路由 {route} 连接失败，尝试切换...")
                self._mark_route_failed(route)
                time.sleep(1)
                continue
                
            except requests.exceptions.Timeout:
                print(f"⚠️ 路由 {route} 超时，尝试切换...")
                self._mark_route_failed(route)
                time.sleep(1)
                continue
                
            except requests.exceptions.RequestException as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Agnes AI 请求失败: {e}")
                print(f"⚠️ 请求异常 (尝试 {attempt+1}/{max_attempts}): {e}")
                time.sleep(2)
                continue
        
        raise Exception("Agnes AI 所有路由均不可用，请稍后重试")
    
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
        
        # ✅ Agnes 的 seed 范围：-1 到 999
        if seed is not None:
            if seed > 999:
                seed = seed % 1000
            elif seed < -1:
                seed = -1
        
        data = {
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "url",
        }
        
        if seed is not None:
            data["seed"] = seed
        
        # ✅ 支持 steps 参数（如果模型支持）
        if steps and steps > 0:
            data["steps"] = steps
        
        # ✅ 支持 guidance_scale
        if cfg and cfg > 0:
            data["guidance_scale"] = cfg
        
        print(f"🔍 Agnes AI 文生图")
        print(f"🔍 模型: {self.image_model}, 尺寸: {size}, 步数: {steps}")
        
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
    
    # api_engines/agnes.py - 完整的 image_to_image 方法

    def image_to_image(
        self,
        prompt: str,
        image: Image.Image,
        strength: float = 0.7,
        width: int = None,
        height: int = None,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """
        图生图 - 使用 OpenAI 兼容格式
        """
        # 获取尺寸
        if width is None or height is None:
            width, height = image.size
        
        # 限制最大尺寸
        max_size = 1024
        if width > max_size or height > max_size:
            scale = max_size / max(width, height)
            width = int(width * scale)
            height = int(height * scale)
            width = ((width + 7) // 8) * 8
            height = ((height + 7) // 8) * 8
        
        size = self._get_size(width, height)
        
        # Agnes 的 seed 范围：-1 到 999
        if seed is not None:
            if seed > 999:
                seed = seed % 1000
            elif seed < -1:
                seed = -1
        
        # 将图片转为 Base64
        img_base64 = self._image_to_base64(image)
        
        # ✅ 构建请求数据（不包含 response_format）
        data = {
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "image": f"data:image/png;base64,{img_base64}",
        }
        
        if seed is not None:
            data["seed"] = seed
        
        if steps and steps > 0:
            data["steps"] = steps
        
        if cfg and cfg > 0:
            data["guidance_scale"] = cfg
        
        if strength and 0 < strength < 1:
            data["strength"] = strength
        
        print(f"🔍 Agnes AI 图生图")
        print(f"🔍 模型: {self.image_model}, 尺寸: {size}, 强度: {strength}")
        print(f"🔍 请求参数: {list(data.keys())}")
        
        # 发送请求
        result = self._request("images/generations", data)
        
        # 解析图片 URL
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
            
            print()
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
        
        # ✅ 使用官方端点 /videos/generations
        result = self._request("videos/generations", data, timeout=300)
        return result
    
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
        return {"info": "请登录 https://platform.agnes-ai.com/ 查看使用量"}
    
    def get_name(self) -> str:
        return f"Agnes AI (图像: {self.image_model}, 文本: {self.text_model})"
    
    def get_model(self) -> str:
        return self.image_model