# application/__init__.py
"""应用层：无 UI 依赖的业务编排。

  events        - EventBus（事件总线）
  context       - AppContext（handler 眼里的 "app"）
  orchestrator  - Orchestrator（业务编排）
"""

from .events import EventBus, Event
from .context import AppContext
from .orchestrator import Orchestrator

__all__ = ["EventBus", "Event", "AppContext", "Orchestrator"]