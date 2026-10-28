# providers/adapters/ollama.py
import requests
import logging
from ..base import BaseProvider, TextRequest
from ..registry import register
from ..errors import ProviderUnavailable

logger = logging.getLogger(__name__)

@register(
    name="ollama_local",
    capabilities=["text"],
    requires_key=False,
    free=True,
    description="本地 Ollama 大语言模型"
)
class OllamaAdapter(BaseProvider):
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen"):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def chat(self, req: TextRequest) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": req.prompt,
            "system": req.system_prompt,
            "stream": False,
            "options": {"temperature": req.temperature}
        }
        
        try:
            res = requests.post(url, json=payload, timeout=60)
            res.raise_for_status()
            return res.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama 请求失败: {e}")
            raise ProviderUnavailable(f"Ollama 连接失败: {e}")