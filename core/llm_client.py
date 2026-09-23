# core/llm_client.py
"""统一 LLM 客户端：Agnes 优先，Ollama 兜底。

设计要点：
  - 后端可插拔：默认顺序 [agnes, ollama]，可通过 LLM_BACKENDS 环境变量覆盖
  - 配置来源优先级：构造参数 > config.settings > 硬编码默认值
  - Agnes engine 缓存：同一实例内只初始化一次，避免重复建连 / 日志噪音
  - chat() 保留 role 语义：不再把 assistant 回复拍平成 user 输入
  - stop / max_tokens / temperature / timeout 全参数透传到各后端
  - strict 模式：所有后端失败时抛异常，便于上层捕获

用法：
    llm = LLMClient()
    text = llm.generate("用一句话介绍 Python")

    # 只走 Ollama
    llm = LLMClient(backends=["ollama"])

    # 关闭兜底（失败直接抛异常）
    llm = LLMClient(strict=True)

    # 多轮对话
    text = llm.chat([
        {"role": "system",    "content": "你是诗人"},
        {"role": "user",      "content": "写两句关于月亮的诗"},
    ])

    # 各 skill 内部推荐用法
    from core.llm_client import get_default_client
    llm = get_default_client(temperature=0.3, max_tokens=512)
    text = llm.generate(prompt)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

logger = logging.getLogger(__name__)

# core/llm_client.py → parents[0]=core/, parents[1]=项目根
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 硬上限，防止调用方传入过大的 max_tokens
MAX_TOKENS_CAP = 8192

# 硬编码默认值（settings 和参数都没有时的最后兜底）
_FALLBACK_BACKENDS: List[str] = ["agnes", "ollama"]
_FALLBACK_OLLAMA_URL = "http://localhost:11434"
_FALLBACK_OLLAMA_MODEL = "qwen2.5:7b"
_FALLBACK_TIMEOUT = 120
_FALLBACK_TEMPERATURE = 0.7
_FALLBACK_MAX_TOKENS = 2048


def _load_settings():
    """安全加载 config.settings，失败返回 None（避免导入期崩溃）。"""
    try:
        from config.settings import settings
        return settings
    except Exception as e:
        logger.warning(f"⚠️ 无法加载 config.settings，将使用硬编码默认值: {e}")
        return None


class LLMClient:
    """所有 skill 共用的 LLM 入口。"""

    DEFAULT_BACKENDS: List[str] = _FALLBACK_BACKENDS

    def __init__(
        self,
        backends: Optional[Sequence[str]] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        strict: bool = False,
    ) -> None:
        """
        Args:
            backends:     后端优先级列表，如 ["agnes", "ollama"]。
                          不传则读 settings.llm_backends，再回退 DEFAULT_BACKENDS。
            ollama_url:   Ollama 服务地址。不传则读 settings.ollama_url。
            ollama_model: Ollama 模型名。不传则读 settings.ollama_model。
            timeout:      单次请求超时（秒）
            temperature:  采样温度
            max_tokens:   最大生成 token 数（超过 MAX_TOKENS_CAP 会被截断）
            strict:       True 时，所有后端失败会抛异常；False 时返回空字符串
        """
        s = _load_settings()

        # ---- backends ----
        if backends:
            self.backends = list(backends)
        elif s is not None and getattr(s, "llm_backends", None):
            self.backends = list(s.llm_backends)
        else:
            self.backends = list(self.DEFAULT_BACKENDS)

        # ---- ollama_url ----
        if ollama_url:
            self.ollama_url = ollama_url.rstrip("/")
        elif s is not None and getattr(s, "ollama_url", None):
            self.ollama_url = str(s.ollama_url).rstrip("/")
        else:
            self.ollama_url = _FALLBACK_OLLAMA_URL

        # ---- ollama_model ----
        if ollama_model:
            self.ollama_model = ollama_model
        elif s is not None and getattr(s, "ollama_model", None):
            self.ollama_model = s.ollama_model
        else:
            self.ollama_model = _FALLBACK_OLLAMA_MODEL

        # ---- timeout ----
        if timeout is not None:
            self.timeout = int(timeout)
        elif s is not None and getattr(s, "llm_timeout", None):
            self.timeout = int(s.llm_timeout)
        else:
            self.timeout = _FALLBACK_TIMEOUT

        # ---- temperature ----
        if temperature is not None:
            self.temperature = float(temperature)
        elif s is not None and getattr(s, "llm_temperature", None):
            self.temperature = float(s.llm_temperature)
        else:
            self.temperature = _FALLBACK_TEMPERATURE

        # ---- max_tokens ----
        if max_tokens is not None:
            self.max_tokens = min(int(max_tokens), MAX_TOKENS_CAP)
        elif s is not None and getattr(s, "llm_max_tokens", None):
            self.max_tokens = min(int(s.llm_max_tokens), MAX_TOKENS_CAP)
        else:
            self.max_tokens = _FALLBACK_MAX_TOKENS

        self.strict = strict

        # ✅ 缓存 Agnes engine（懒加载，同一实例只建一次）
        self._agnes_engine = None

        logger.debug(
            f"LLMClient 初始化: backends={self.backends}, "
            f"ollama={self.ollama_url}/{self.ollama_model}, "
            f"timeout={self.timeout}, temperature={self.temperature}, "
            f"max_tokens={self.max_tokens}"
        )

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        stop: Optional[Union[str, Sequence[str]]] = None,
        **kw: Any,
    ) -> str:
        """单轮生成。

        Args:
            prompt: 用户输入
            system: 系统提示词（可选）
            stop:   停止串（字符串或字符串列表，可选）
            **kw:   可覆盖 temperature / max_tokens / timeout

        Returns:
            模型输出文本；所有后端失败时返回 ""（strict=True 则抛异常）
        """
        temperature = kw.pop("temperature", self.temperature)
        max_tokens = min(kw.pop("max_tokens", self.max_tokens), MAX_TOKENS_CAP)
        timeout = kw.pop("timeout", self.timeout)

        if kw:
            logger.warning(f"⚠️ generate() 收到未识别的参数: {list(kw.keys())}")

        stop_list = self._normalize_stop(stop)

        for backend in self.backends:
            try:
                if backend == "agnes":
                    text = self._agnes(prompt, system, temperature, max_tokens, stop_list)
                elif backend == "ollama":
                    text = self._ollama(prompt, system, temperature, max_tokens, timeout, stop_list)
                else:
                    logger.warning(f"未知 LLM 后端: {backend}")
                    continue

                if text:
                    logger.info(f"✅ LLM 后端命中: {backend} ({len(text)} 字)")
                    return text
                logger.warning(f"⚠️ LLM 后端 {backend} 返回空")

            except RuntimeError as e:
                logger.warning(f"⚠️ LLM 后端 {backend} 配置错误: {e}")
            except Exception as e:
                logger.warning(f"⚠️ LLM 后端 {backend} 调用失败: {e}")

        if self.strict:
            raise RuntimeError("所有 LLM 后端均失败")
        logger.error("❌ 所有 LLM 后端均失败，返回空")
        return ""

    def chat(
        self,
        messages: Sequence[Dict[str, Any]],
        **kw: Any,
    ) -> str:
        """多轮对话。

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
                      content 可为字符串，或 OpenAI 风格的多模态数组
            **kw:     透传给 generate()

        Returns:
            模型输出文本
        """
        temperature = kw.pop("temperature", self.temperature)
        max_tokens = min(kw.pop("max_tokens", self.max_tokens), MAX_TOKENS_CAP)
        timeout = kw.pop("timeout", self.timeout)
        stop = kw.pop("stop", None)
        stop_list = self._normalize_stop(stop)

        if kw:
            logger.warning(f"⚠️ chat() 收到未识别的参数: {list(kw.keys())}")

        for backend in self.backends:
            try:
                if backend == "agnes":
                    text = self._agnes_chat(messages, temperature, max_tokens, stop_list)
                elif backend == "ollama":
                    text = self._ollama_chat(messages, temperature, max_tokens, timeout, stop_list)
                else:
                    logger.warning(f"未知 LLM 后端: {backend}")
                    continue

                if text:
                    logger.info(f"✅ LLM 后端命中: {backend} ({len(text)} 字)")
                    return text
                logger.warning(f"⚠️ LLM 后端 {backend} 返回空")

            except RuntimeError as e:
                logger.warning(f"⚠️ LLM 后端 {backend} 配置错误: {e}")
            except Exception as e:
                logger.warning(f"⚠️ LLM 后端 {backend} 调用失败: {e}")

        if self.strict:
            raise RuntimeError("所有 LLM 后端均失败")
        logger.error("❌ 所有 LLM 后端均失败，返回空")
        return ""

    # ------------------------------------------------------------------
    # 后端实现：Agnes
    # ------------------------------------------------------------------

    def _get_agnes_engine(self):
        """懒加载并缓存 Agnes engine。"""
        if self._agnes_engine is not None:
            return self._agnes_engine

        from api_engines import create_engine
        from config.settings import settings

        if not settings.agnes_api_key:
            raise RuntimeError("未配置 AGNES_API_KEY")

        engine = create_engine("agnes", {
            "AGNES_API_KEY": settings.agnes_api_key,
            "AGNES_BASE_URL": settings.agnes_base_url,
            "AGNES_IMAGE_MODEL": settings.agnes_image_model,
            "AGNES_TEXT_MODEL": settings.agnes_text_model,
        })
        self._agnes_engine = engine
        return engine

    def _agnes(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        stop_list: List[str],
    ) -> str:
        engine = self._get_agnes_engine()

        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return self._call_agnes_engine(engine, messages, temperature, max_tokens, stop_list)

    def _agnes_chat(
        self,
        messages: Sequence[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        stop_list: List[str],
    ) -> str:
        engine = self._get_agnes_engine()
        return self._call_agnes_engine(engine, messages, temperature, max_tokens, stop_list)

    def _call_agnes_engine(
        self,
        engine,
        messages: Sequence[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        stop_list: List[str],
    ) -> str:
        """统一调用 Agnes engine.chat()。"""
        kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if stop_list:
            kwargs["stop"] = stop_list

        try:
            text = engine.chat(messages=list(messages), **kwargs)
        except TypeError:
            # 兼容不支持 stop 参数的旧版 engine
            kwargs.pop("stop", None)
            text = engine.chat(messages=list(messages), **kwargs)

        return (text or "").strip()

    # ------------------------------------------------------------------
    # 后端实现：Ollama
    # ------------------------------------------------------------------

    def _ollama(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        timeout: int,
        stop_list: List[str],
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": self._ollama_options(temperature, max_tokens, stop_list),
        }
        if system:
            payload["system"] = system
        return self._post_ollama_generate(payload, timeout)

    def _ollama_chat(
        self,
        messages: Sequence[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout: int,
        stop_list: List[str],
    ) -> str:
        """用 /api/chat 保留 role 语义。"""
        payload: Dict[str, Any] = {
            "model": self.ollama_model,
            "messages": [self._normalize_message(m) for m in messages],
            "stream": False,
            "options": self._ollama_options(temperature, max_tokens, stop_list),
        }
        return self._post_ollama_chat(payload, timeout)

    @staticmethod
    def _ollama_options(
        temperature: float,
        max_tokens: int,
        stop_list: List[str],
    ) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        if stop_list:
            opts["stop"] = stop_list
        return opts

    def _post_ollama_generate(self, payload: Dict[str, Any], timeout: int) -> str:
        url = f"{self.ollama_url}/api/generate"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"无法连接 Ollama ({self.ollama_url}): {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama 请求超时 ({timeout}s)")

        if r.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:120]}")
        return (r.json().get("response") or "").strip()

    def _post_ollama_chat(self, payload: Dict[str, Any], timeout: int) -> str:
        url = f"{self.ollama_url}/api/chat"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"无法连接 Ollama ({self.ollama_url}): {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama 请求超时 ({timeout}s)")

        if r.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:120]}")
        data = r.json()
        # /api/chat 返回 {message: {role, content}, ...}
        return ((data.get("message") or {}).get("content") or "").strip()

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_stop(stop: Optional[Union[str, Sequence[str]]]) -> List[str]:
        """把 stop 参数统一成 list[str]。"""
        if not stop:
            return []
        if isinstance(stop, str):
            return [stop]
        return [s for s in stop if s]

    @staticmethod
    def _normalize_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """把消息规整成 Ollama /api/chat 能吃的格式。"""
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append(p.get("text", ""))
            content = " ".join(parts)
        return {"role": role, "content": content}


# ------------------------------------------------------------------
# 便捷入口
# ------------------------------------------------------------------

def get_default_client(**overrides) -> LLMClient:
    """获取一个带全局默认配置的 LLMClient。

    用途：让各 skill 一行调用，不用关心环境变量名。

    Args:
        **overrides: 覆盖项，如 backends=["ollama"]、timeout=30

    Returns:
        LLMClient 实例

    示例：
        from core.llm_client import get_default_client
        llm = get_default_client(temperature=0.3, max_tokens=512)
        text = llm.generate("写一句诗")
    """
    return LLMClient(**overrides)