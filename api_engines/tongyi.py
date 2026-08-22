"""通义万相 API 图像生成引擎 - 自动判断 API Key 类型"""

import os
import base64
import requests
from PIL import Image
import io
import json
from typing import Optional

try:
    import dashscope
    from dashscope import ImageSynthesis
except ImportError:
    dashscope = None


class TongyiEngine:
    """通义万相 API 引擎 (自动适配百炼/DashScope)"""
    
    def __init__(self, api_key: str, model: str = "wanx-v1", base_url: str = None):
        self.api_key = api_key
        self.model = model or "wanx-v1"
        
        # 百炼网关地址
        self.base_url = base_url or os.getenv("TONGYI_BASE_URL", 
            "https://ws-fxkdf5ftr2crttee.ap-southeast-1.maas.aliyuncs.com")
        
        # 支持的尺寸
        self.supported_sizes = [
            "512*512", "1024*1024", "1024*768", "768*1024",
            "1280*720", "720*1280", "1280*768", "768*1280"
        ]
        
        # qwen-image-plus 支持的尺寸
        self.qwen_sizes = [
            "1664*928", "1472*1104", "1328*1328", 
            "1104*1472", "928*1664"
        ]
        
        # 判断 API Key 类型
        self._detect_api_type()
    
    def _detect_api_type(self):
        """检测 API Key 类型"""
        if not self.api_key:
            self.api_type = "unknown"
            return
        
        if self.api_key.startswith("sk-ws-"):
            # 百炼 API Key
            self.api_type = "bailian"
            print("🔍 检测到百炼 API Key，使用百炼 HTTP API")
        elif self.api_key.startswith("sk-"):
            # DashScope API Key
            self.api_type = "dashscope"
            print("🔍 检测到 DashScope API Key，使用 DashScope SDK")
        else:
            self.api_type = "unknown"
            print("⚠️ 未知 API Key 格式，尝试百炼模式")
    
    def _get_size(self, width: int, height: int, model: str = None) -> str:
        """获取支持的尺寸"""
        size = f"{width}*{height}"
        model = model or self.model
        
        # qwen-image-plus 系列使用特定尺寸
        if "qwen-image" in model:
            if size in self.qwen_sizes:
                return size
            # 找最接近的
            aspect = width / height
            best_match = "1328*1328"
            best_diff = float('inf')
            for s in self.qwen_sizes:
                w, h = map(int, s.split('*'))
                diff = abs(aspect - w/h)
                if diff < best_diff:
                    best_diff = diff
                    best_match = s
            return best_match
        
        # 其他模型使用标准尺寸
        if size in self.supported_sizes:
            return size
        
        aspect = width / height
        best_match = "1024*1024"
        best_diff = float('inf')
        for s in self.supported_sizes:
            w, h = map(int, s.split('*'))
            diff = abs(aspect - w/h)
            if diff < best_diff:
                best_diff = diff
                best_match = s
        
        return best_match
    
    def generate_single(
        self,
        prompt: str,
        negative: str = "worst quality, low quality, ugly, deformed",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """生成单张图片 - 自动选择调用方式"""
        
        if not self.api_key:
            raise ValueError("请设置 TONGYI_API_KEY")
        
        # 根据 API 类型选择调用方式
        if self.api_type == "dashscope":
            return self._generate_with_dashscope(
                prompt, negative, width, height, steps, cfg, seed
            )
        else:
            # 默认使用百炼 HTTP API（也支持未知类型）
            return self._generate_with_bailian(
                prompt, negative, width, height, steps, cfg, seed
            )
    
    def _generate_with_dashscope(
        self,
        prompt: str,
        negative: str,
        width: int,
        height: int,
        steps: int,
        cfg: float,
        seed: int,
    ) -> Image.Image:
        """使用 DashScope SDK 生成"""
        
        if not dashscope:
            raise ImportError("请安装 dashscope: pip install dashscope")
        
        size = self._get_size(width, height)
        
        # 设置 DashScope
        dashscope.api_key = self.api_key
        
        print(f"🔍 [DashScope] 模型: {self.model}")
        print(f"🔍 [DashScope] 尺寸: {size}")
        
        try:
            response = ImageSynthesis.call(
                model=self.model,
                prompt=prompt,
                negative_prompt=negative,
                n=1,
                size=size,
                step=steps,
                cfg_scale=cfg,
                seed=seed,
            )
            
            if response.status_code != 200:
                error_msg = f"DashScope API 调用失败: {response.message}"
                if hasattr(response, 'code') and response.code:
                    error_msg += f" (错误码: {response.code})"
                raise Exception(error_msg)
            
            # 解析图片
            image_url = response.output.results[0].url
            
            if image_url.startswith("data:image"):
                import re
                base64_data = re.sub(r"^data:image/.+;base64,", "", image_url)
                image_bytes = base64.b64decode(base64_data)
                return Image.open(io.BytesIO(image_bytes))
            
            img_response = requests.get(image_url, timeout=30)
            if img_response.status_code != 200:
                raise Exception(f"下载图片失败: {img_response.status_code}")
            return Image.open(io.BytesIO(img_response.content))
            
        except Exception as e:
            raise Exception(f"DashScope 生成失败: {e}")
    
    def _generate_with_bailian(
        self,
        prompt: str,
        negative: str,
        width: int,
        height: int,
        steps: int,
        cfg: float,
        seed: int,
    ) -> Image.Image:
        """使用百炼 HTTP API 生成"""
        
        size = self._get_size(width, height)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建请求
        data = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            "parameters": {
                "size": size,
                "n": 1,
                "cfg_scale": cfg,
                "step": steps,
            }
        }
        
        # 添加可选参数
        if seed is not None:
            data["parameters"]["seed"] = seed
        if negative:
            data["input"]["negative_prompt"] = negative
        
        # 尝试多个端点
        endpoints = [
            f"{self.base_url}/api/v1/services/aigc/multimodal-generation/generation",
            f"{self.base_url}/compatible-mode/v1/chat/completions",
        ]
        
        last_error = None
        
        for url in endpoints:
            try:
                print(f"🔍 [百炼] 尝试端点: {url}")
                print(f"🔍 [百炼] 模型: {self.model}")
                print(f"🔍 [百炼] 尺寸: {size}")
                
                # 如果是 OpenAI 兼容端点，调整数据格式
                if "compatible-mode" in url:
                    openai_data = {
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "parameters": {
                            "size": size,
                            "n": 1,
                            "cfg_scale": cfg,
                            "step": steps,
                            "negative_prompt": negative
                        }
                    }
                    if seed is not None:
                        openai_data["parameters"]["seed"] = seed
                    response_data = openai_data
                else:
                    response_data = data
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=response_data,
                    timeout=120
                )
                
                print(f"🔍 [百炼] 响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 解析图片 URL
                    image_url = self._extract_image_url(result, url)
                    if image_url:
                        print(f"🔍 [百炼] 获取到图片URL")
                        return self._download_image(image_url)
                    else:
                        print(f"🔍 [百炼] 未找到图片URL，响应: {json.dumps(result, indent=2)[:500]}")
                        continue
                
                elif response.status_code == 400:
                    try:
                        error_json = response.json()
                        error_msg = error_json.get('message', str(error_json))
                        print(f"🔍 [百炼] 400错误: {error_msg[:200]}")
                        last_error = error_msg
                        # 如果是 url error，可能端点不对，继续尝试下一个
                        if "url error" in error_msg:
                            continue
                    except:
                        last_error = response.text
                    continue
                else:
                    print(f"🔍 [百炼] 非200状态码: {response.status_code}")
                    continue
                    
            except Exception as e:
                print(f"🔍 [百炼] 端点请求失败: {e}")
                last_error = str(e)
                continue
        
        raise Exception(f"百炼 API 调用失败: {last_error or '所有端点均失败'}")
    
    def _extract_image_url(self, result: dict, url: str) -> Optional[str]:
        """从响应中提取图片 URL"""
        
        # 百炼标准格式
        if 'output' in result:
            output = result['output']
            if 'results' in output and output['results']:
                return output['results'][0].get('url')
            if 'data' in output and output['data']:
                return output['data'][0].get('url')
            if 'image_url' in output:
                return output['image_url']
        
        # OpenAI 兼容格式
        if 'data' in result and result['data']:
            return result['data'][0].get('url')
        
        # Chat 格式
        if 'choices' in result and result['choices']:
            content = result['choices'][0].get('message', {}).get('content', '')
            if content.startswith('http'):
                return content
            if content.startswith('{'):
                try:
                    content_data = json.loads(content)
                    return content_data.get('url') or content_data.get('image_url')
                except:
                    pass
        
        return None
    
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
    
    def get_usage(self):
        return {"info": "请登录阿里云控制台查看使用量"}
    
    def get_name(self) -> str:
        return f"通义万相 ({self.model})"