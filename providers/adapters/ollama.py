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
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip('/')
        self.model = model

    @classmethod
    def from_config(cls, config: dict):
        return cls(
            base_url=config.get("base_url", "http://127.0.0.1:11434"),
            model=config.get("model", "qwen2.5:7b")
        )

    def chat(self, req: TextRequest) -> str:
        url = f"{self.base_url}/api/chat"
        
        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": req.temperature}
        }
        
        try:
            logger.info(f"🧠 请求 Ollama ({self.model}): {req.prompt[:20]}...")
            
            # ★ 核心修复：强制绕过系统代理（Clash/V2Ray 等会导致本地请求 404）
            proxies = {
                "http": None,
                "https": None,
            }
            
            res = requests.post(url, json=payload, timeout=120, proxies=proxies)
            
            # 如果返回 404，打印具体报错内容
            if res.status_code == 404:
                logger.error(f"❌ Ollama 返回 404，可能是代理拦截或路径错误。响应内容: {res.text}")
                
            res.raise_for_status()
            return res.json().get("message", {}).get("content", "")
            
        except Exception as e:
            logger.error(f"❌ Ollama 请求失败: {e}")
            raise ProviderUnavailable(f"Ollama 连接失败: {e}")