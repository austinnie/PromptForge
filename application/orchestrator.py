# application/orchestrator.py
"""应用层业务编排。所有端（GUI/CLI/Web/手机）共享同一个 Orchestrator。"""

from __future__ import annotations

import importlib
import logging
import threading
from dataclasses import asdict
from typing import Optional

from core.intent_analyzer import IntentAnalyzer
from core.context_manager import ContextManager

from .context import AppContext

logger = logging.getLogger(__name__)


# IntentResult.type → handler 名
_INTENT_TO_HANDLER = {
    "text_to_image": "text_to_image",
    "image_to_image": "image_to_image",
    "couple": "couple",
    "multi_person": "multi_person",
    "preset_image": "preset",
    "video": "video",
    "skill": "skill",
    "chat": "chat",
    "model_manage": "skill",   # local_model_manage 走 skill 路由
}

# handler 名 → (module, class)
_HANDLER_IMPORT = {
    "text_to_image": ("handlers.text_to_image", "TextToImageHandler"),
    "image_to_image": ("handlers.image_to_image", "ImageToImageHandler"),
    "couple": ("handlers.couple_handler", "CoupleHandler"),
    "multi_person": ("handlers.multi_person_handler", "MultiPersonHandler"),
    "preset": ("handlers.preset_handler", "PresetHandler"),
    "video": ("handlers.video_handler", "VideoHandler"),
    "skill": ("handlers.skill_handler", "SkillHandler"),
    "chat": ("handlers.chat_handler", "ChatHandler"),
}


class Orchestrator:
    """业务编排。"""

    def __init__(self, bus, ctx: AppContext, pre_dispatch_hook=None):
        self.bus = bus
        self.ctx = ctx
        self.settings = ctx.settings
        self.pre_dispatch_hook = pre_dispatch_hook

        self.intent = IntentAnalyzer()

        # ContextManager（对话历史）
        if ctx.context is None:
            ctx.context = ContextManager()
        self.memory = ctx.context

        self._handlers: dict = {}
        self._lock = threading.Lock()
        self._busy = False

    # ============================================================
    # 主入口
    # ============================================================

    def handle_text(self, text: str, images: list = None) -> None:
        """处理用户输入。所有端唯一入口。"""
        with self._lock:
            if self._busy:
                self.bus.emit(
                    "message",
                    role="assistant",
                    content="⏳ 正在处理中，请稍候...",
                )
                return
            self._busy = True

        try:
            if images is not None:
                self.ctx.uploaded_images = list(images)

            self.bus.emit("status", text="🎯 分析意图...")
            intent = self.intent.analyze(
                text,
                has_image=bool(self.ctx.uploaded_images),
                has_multiple=len(self.ctx.uploaded_images) >= 2,
                image_count=len(self.ctx.uploaded_images),
            )
            self.bus.emit("status", text=f"🎯 {intent.type}")

            if intent.system_hint:
                self.bus.emit("message", role="assistant", content=intent.system_hint)

            self._dispatch(intent)

        except Exception as e:
            logger.exception("Orchestrator.handle_text 失败")
            self.bus.emit("error", message=str(e))
        finally:
            with self._lock:
                self._busy = False

    def run_skill(self, name: str, **kwargs) -> None:
        """显式调用 skill（GUI 菜单 / CLI 命令）。"""
        with self._lock:
            if self._busy:
                self.bus.emit("message", role="assistant", content="⏳ 正在处理中")
                return
            self._busy = True

        try:
            from skills.registry import get_meta, import_skill_class

            meta = get_meta(name)
            if meta is None:
                self.bus.emit("error", message=f"未知 skill: {name}")
                return


            # 用 kwargs_builder 生成默认参数，再用用户传入的覆盖
            defaults = {}
            if meta.kwargs_builder:
                try:
                    built = meta.kwargs_builder({"prompt": "", "original_text": ""})
                    if built:
                        defaults = dict(built)
                except Exception as e:
                    logger.warning(f"kwargs_builder 失败 (skill={name}): {e}")

            # 用户传的覆盖默认值
            merged = {**defaults, **kwargs}
            if defaults:
                logger.info(
                    f"skill={name} defaults={defaults} user={kwargs} merged={merged}"
                )
            kwargs = merged

            # 回显实际参数（CLI/Web 用）
            self.bus.emit("skill_start", name=name, kwargs=kwargs)
            
            cls = import_skill_class(meta)
            instance = cls(self._build_skill_config())

            self.bus.emit("status", text=f"⏳ {meta.system_hint or name}...")
            result = instance.execute(**kwargs)

            if isinstance(result, dict) and result.get("status") == "success":
                self.bus.emit("message", role="assistant", content=f"✅ {name} 完成")
                for key in (
                    "image_path", "video_path", "audio_file",
                    "article_path", "preview_path", "report_file",
                    "repo_url", "saved_to", "article_dir",
                ):
                    v = result.get("result", {}).get(key)
                    if v:
                        self.bus.emit("artifact", kind=key, path=str(v))
            else:
                err = (result or {}).get("error", "未知错误") if isinstance(result, dict) else str(result)
                self.bus.emit("error", message=f"{name} 失败: {err}")

            self.bus.emit("skill_done", name=name, result=result or {})

        except Exception as e:
            logger.exception(f"run_skill({name}) 失败")
            self.bus.emit("error", message=str(e))
        finally:
            with self._lock:
                self._busy = False

    def cancel(self) -> None:
        """取消当前任务。"""
        for h in self._handlers.values():
            if hasattr(h, "cancel"):
                try:
                    h.cancel()
                except Exception:
                    pass
        self.bus.emit("status", text="⏹️ 已请求取消")

    # ============================================================
    # 内部
    # ============================================================

    def _get_handler(self, name: str):
        if name in self._handlers:
            return self._handlers[name]
        if name not in _HANDLER_IMPORT:
            raise ValueError(f"未知 handler: {name}")

        module_path, class_name = _HANDLER_IMPORT[name]
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        handler = cls(self.ctx)
        self._handlers[name] = handler
        return handler

    def _dispatch(self, intent) -> None:
        # 前置钩子（GUI 用于 LLM 增强等）
        if self.pre_dispatch_hook:
            try:
                self.pre_dispatch_hook(intent)
            except Exception as e:
                logger.warning(f"pre_dispatch_hook 失败: {e}")
                
        handler_name = _INTENT_TO_HANDLER.get(intent.type)
        if handler_name is None:
            self.bus.emit("error", message=f"未知意图: {intent.type}")
            return

        handler = self._get_handler(handler_name)

        # IntentResult(dataclass) → dict（handler.handle 要 dict）
        if hasattr(intent, "__dataclass_fields__"):
            intent_dict = asdict(intent)
        else:
            intent_dict = dict(intent)

        handler.handle(intent_dict)

    def _build_skill_config(self) -> dict:
        s = self.settings
        return {
            "output_dir": str(s.output_dir),
            "log_level": "INFO",
        }

    # ============================================================
    # 状态
    # ============================================================

    @property
    def busy(self) -> bool:
        return self._busy

    def get_status(self) -> dict:
        return {
            "busy": self._busy,
            "handlers_loaded": list(self._handlers.keys()),
            "uploaded_images": len(self.ctx.uploaded_images),
        }