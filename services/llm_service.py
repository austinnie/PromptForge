# services/llm_service.py
"""LLMService - 兼容旧接口的薄壳。

历史：
  早期这里是「直接调 Ollama /api/generate」的实现。
  后来项目引入 core.llm_client.LLMClient（Agnes 优先，Ollama 兜底），
  这里改成薄壳，保留旧 API 语义，内部全部走 LLMClient。

使用建议：
  - 新代码直接用 `from core.llm_client import get_default_client`
  - 老代码 `self.llm = LLMService()` 不用改，行为会自动升级
"""

from __future__ import annotations

import logging
import requests
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务 - 兼容旧接口。

    旧签名: LLMService(base_url="http://localhost:11434", model="qwen2.5:1.5b")
    新行为: 内部走 LLMClient，默认只走 ollama（保持旧语义），
            如需走 Agnes，请直接构造 LLMClient(backends=["agnes","ollama"])。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model

        # 延迟初始化 LLMClient，避免 import 循环
        self._client = None

        # 保留旧字段，兼容外部读
        self._available = False
        self._checked = False

    # ---------- 内部：懒加载 LLMClient ----------

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from core.llm_client import LLMClient
            self._client = LLMClient(
                backends=["ollama"],           # 旧接口默认只走 ollama
                ollama_url=self.base_url,
                ollama_model=self.model,
            )
            return self._client
        except Exception as e:
            logger.error(f"⚠️ LLMClient 初始化失败: {e}")
            self._client = False   # 负缓存，防止每次重试
            return None

    # ---------- 兼容旧接口 ----------

    def is_running(self) -> bool:
        """检查 Ollama 是否运行（旧逻辑，直接探活）"""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def is_available(self) -> bool:
        """检查模型是否可用（旧逻辑）"""
        if not self._checked:
            self._check()
        return self._available

    def _check(self):
        self._checked = True
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if r.status_code != 200:
                self._available = False
                return
            models = [m.get("name", "") for m in r.json().get("models", [])]
            # 精确匹配 or 前缀匹配（qwen2.5 命中 qwen2.5:1.5b）
            self._available = (
                self.model in models
                or any(self.model.split(":")[0] in m for m in models)
            )
        except Exception:
            self._available = False

    def generate(
        self,
        prompt: str,
        timeout: int = 30,
        max_tokens: int = 512,
        **kw: Any,
    ) -> Optional[str]:
        """生成文本（内部走 LLMClient）"""
        client = self._get_client()
        if not client:
            return None

        text = client.generate(
            prompt,
            timeout=timeout,
            max_tokens=max_tokens,
            **kw,
        )
        return text or None

    def get_status_message(self) -> str:
        if not self.is_running():
            return "⚠️ Ollama 服务未运行"
        if not self.is_available():
            return f"⚠️ 模型 {self.model} 未下载"
        return "✅ LLM 服务正常"