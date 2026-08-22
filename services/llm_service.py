# services/llm_service.py
import requests
from typing import Optional


class LLMService:
    """LLM服务 - 封装Ollama调用"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b"):
        self.base_url = base_url
        self.model = model
        self._available = False
        self._checked = False
    
    def is_running(self) -> bool:
        """检查Ollama服务是否运行"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except:
            return False
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        if not self._checked:
            self._check()
        return self._available
    
    def _check(self):
        """检查并缓存状态"""
        self._checked = True
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                self._available = self.model in models or self.model.split(":")[0] in str(models)
            return
        except:
            self._available = False
    
    def generate(self, prompt: str, timeout: int = 30, max_tokens: int = 512) -> Optional[str]:
        """生成文本"""
        if not self.is_available():
            return None
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.7,
                    "stream": False,
                    "max_tokens": max_tokens,
                },
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except:
            pass
        return None
    
    def get_status_message(self) -> str:
        """获取状态消息"""
        if not self.is_running():
            return "⚠️ Ollama 服务未运行"
        if not self.is_available():
            return f"⚠️ 模型 {self.model} 未下载"
        return "✅ LLM 服务正常"