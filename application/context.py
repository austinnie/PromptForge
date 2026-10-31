# application/context.py
"""AppContext —— handler 眼里的 "app" 对象。

设计目标：
  - 让现有 8 个 handler 不需要修改就能在 Orchestrator 下工作
  - GUI 端：from_gui() 包装现有 ChatApp，保持同一份状态
  - headless 端：headless() 全走事件总线（CLI / Web / 测试）
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

MessageCallback = Callable[[str, str], None]   # (role, content)
StatusCallback = Callable[[str], None]          # (msg)
ImageCallback = Callable[[str, str], None]      # (path, caption)

class _StatusVar:
    """假的 StringVar，把 set() 转发到回调。"""
    def __init__(self, cb):
        self._cb = cb
        self._value = ""

    def set(self, value: str) -> None:
        self._value = value
        self._cb(value)

    def get(self) -> str:
        return self._value  

class AppContext:
    """handler 用的最小 app 接口。"""

    def __init__(
        self,
        settings,
        *,
        on_message: Optional[MessageCallback] = None,
        on_status: Optional[StatusCallback] = None,
        on_image: Optional[ImageCallback] = None,
        llm: Any = None,
        context_mgr: Any = None,
        load_model: Optional[Callable[[], None]] = None,
    ):
        self.settings = settings
        self.uploaded_images: list = []

        # 回调（默认打 print，headless 时也能看到）
        self._on_message = on_message or (lambda r, c: print(f"[{r}] {c}"))
        self._on_status = on_status or (lambda m: print(f"[status] {m}"))
        self._on_image = on_image

        # handler 会用到的可选字段
        self.llm = llm
        self.context = context_mgr          # ContextManager（对话历史）
        self.pipe = None                    # 本地 pipe 缓存
        self.is_model_loaded = False
        self._load_model_fn = load_model

        # SkillHandler 的并发锁
        self._skill_running = False
        self._skill_current = None

        # BaseHandler._update_status 会 hasattr(app, 'status_var')

        self.status_var = _StatusVar(self._on_status)

    # ---------- handler 调用这些 ----------

    def _append_message(self, role: str, content: str) -> None:
        self._on_message(role, content)

    def _update_status(self, msg: str) -> None:
        self._on_status(msg)

    def _append_image(self, path: str, caption: str = "") -> None:
        if self._on_image:
            self._on_image(path, caption)

    # ---------- 模型加载（base._ensure_model_loaded 用）----------

    def _load_model(self) -> None:
        if self._load_model_fn:
            self._load_model_fn()
            return
        # headless 兜底：预热 local_sd provider
        try:
            from providers.registry import create
            from config.settings import settings as _s
            if getattr(_s, "generation_mode", "api") == "local":
                create("local_sd", {
                    "model_path": _s.model_path,
                    "lora_path": _s.lora_path,
                    "device": "CPU",
                })
                self.is_model_loaded = True
        except Exception as e:
            logger.warning(f"headless _load_model 失败: {e}")

    # ---------- 工厂 ----------

    @classmethod
    def from_gui(cls, gui_app) -> "AppContext":
        def _status_threadsafe(m: str) -> None:
            sv = getattr(gui_app, "status_var", None)
            if sv is None:
                return
            root = getattr(gui_app, "root", None)
            try:
                if root is not None:
                    root.after(0, lambda v=m: sv.set(v))
                else:
                    sv.set(m)
            except Exception:
                pass

        ctx = cls(
            settings=gui_app.settings,
            on_message=gui_app._append_message,
            on_status=_status_threadsafe,
            on_image=getattr(gui_app, "_append_image", None),
            llm=getattr(gui_app, "llm", None),
            load_model=getattr(gui_app, "_load_model", None),
        )
        ctx.uploaded_images = getattr(gui_app, "uploaded_images", [])
        ctx.context = getattr(gui_app, "context", None)
        ctx.pipe = getattr(gui_app, "pipe", None)
        ctx.is_model_loaded = getattr(gui_app, "is_model_loaded", False)
        # handler 通过 status_var.set() 更新状态栏（替代 print [STATUS]）
        ctx.status_var = _StatusVar(_status_threadsafe)
        return ctx

    @classmethod
    def headless(cls, settings, bus=None) -> "AppContext":
        """纯 headless（CLI / Web / 测试）。"""
        ctx = cls(settings=settings)
        if bus is not None:
            ctx._on_message = lambda r, c: bus.emit("message", role=r, content=c)
            ctx._on_status = lambda m: bus.emit("status", text=m)
            ctx._on_image = lambda p, c="": bus.emit("artifact", kind="image", path=p)
        return ctx    
      