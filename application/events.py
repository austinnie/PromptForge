# application/events.py
"""事件总线。

设计：
  - 极简 pub/sub，不依赖 asyncio（GUI 是同步的，Web 是异步的，都能用）
  - 所有 UI 只订阅事件，不直接调 handler
  - 每个 subscriber 的错误被捕获，不影响其它 subscriber

事件类型（约定）：
  message    - 聊天消息  {role, content}
  artifact   - 产物      {kind, path, meta?}
  status     - 状态栏    {text}
  progress   - 进度      {value: 0-100, msg}
  error      - 错误      {message, exc?}
  skill_done - skill 完成 {name, result}
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Event:
    type: str
    payload: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


Handler = Callable[[Event], None]


class EventBus:
    """线程安全的同步事件总线。"""

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}
        self._lock = threading.Lock()

    # ---------- 订阅 ----------

    def on(self, event_type: str, handler: Handler) -> Callable[[], None]:
        """订阅；返回 unsubscribe 函数。event_type="*" 订阅所有。"""
        with self._lock:
            self._subs.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                lst = self._subs.get(event_type, [])
                if handler in lst:
                    lst.remove(handler)

        return unsubscribe

    def once(self, event_type: str, handler: Handler) -> None:
        """只触发一次。"""
        def wrapper(e: Event) -> None:
            try:
                handler(e)
            finally:
                unsubscribe()
        unsubscribe = self.on(event_type, wrapper)

    # ---------- 发布 ----------

    def emit(self, event_type: str, **payload: Any) -> None:
        """同步广播。所有 handler 在调用线程里依次执行。"""
        event = Event(event_type, payload)

        with self._lock:
            handlers = list(self._subs.get(event_type, []))
            wildcard = list(self._subs.get("*", []))

        for h in handlers + wildcard:
            try:
                h(event)
            except Exception:
                logger.exception(
                    f"EventBus handler 异常 (type={event_type}, handler={h})"
                )

    # ---------- 工具 ----------

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()

    def __repr__(self) -> str:
        with self._lock:
            summary = {k: len(v) for k, v in self._subs.items()}
        return f"<EventBus {summary}>"