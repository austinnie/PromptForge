# scripts/cli_chat.py
"""PromptForge 命令行客户端。

用途：
  - 独立验证 Orchestrator 全链路（chat / skill / 生成）
  - 作为 "第二个端"（需求 5 多端的样板）
  - 未来 Web 端的编排逻辑与本文件完全一致

用法：
  python scripts/cli_chat.py
  > github日报
  > 画一只猫
  > /skill news_aggregator
  > /quit
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.events import EventBus, Event
from application.context import AppContext
from application.orchestrator import Orchestrator
from config.settings import settings


# ============================================================
# 事件渲染
# ============================================================

class ConsoleRenderer:
    """把事件渲染到终端。"""

    COLORS = {
        "user": "\033[36m",
        "assistant": "\033[32m",
        "status": "\033[90m",
        "artifact": "\033[33m",
        "error": "\033[31m",
        "reset": "\033[0m",
    }

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._wire()

    def _c(self, kind: str, text: str) -> str:
        c = self.COLORS.get(kind, "")
        r = self.COLORS["reset"]
        return f"{c}{text}{r}" if c else text

    def _wire(self):
        self.bus.on("message", self._on_message)
        self.bus.on("status", self._on_status)
        self.bus.on("artifact", self._on_artifact)
        self.bus.on("error", self._on_error)
        self.bus.on("skill_done", self._on_skill_done)
        self.bus.on("skill_start", self._on_skill_start)

    def _on_skill_start(self, e: Event):
        name = e.get("name", "?")
        kwargs = e.get("kwargs", {})
        print(self._c("status", f"  🚀 skill={name} kwargs={kwargs}"))
        
    def _on_message(self, e: Event):
        role = e.get("role", "assistant")
        content = e.get("content", "")
        tag = self._c(role, f"[{role}]")
        print(f"{tag} {content}")

    def _on_status(self, e: Event):
        print(self._c("status", f"  · {e.get('text', '')}"))

    def _on_artifact(self, e: Event):
        print(self._c("artifact", f"  📄 {e.get('kind')}: {e.get('path')}"))

    def _on_error(self, e: Event):
        print(self._c("error", f"  ❌ {e.get('message', '')}"))

    def _on_skill_done(self, e: Event):
        name = e.get("name")
        result = e.get("result", {})
        status = result.get("status", "?") if isinstance(result, dict) else "?"
        print(self._c("status", f"  · skill={name} status={status}"))


# ============================================================
# 命令处理
# ============================================================

HELP_TEXT = """
命令：
  /help                      显示帮助
  /quit                      退出
  /schema <name>             查看 skill 参数  
  /skill <name> [k=v ...]    显式调用 skill（例: /skill news_aggregator category=tech）
  /list                      列出所有已注册 skill
  /cancel                    取消当前任务
  /status                    查看 orchestrator 状态
  /clear                     清空对话历史
其他任何输入 → 走意图分析（自动分发）
"""


def _parse_kwargs(args: list[str]) -> dict:
    kw = {}
    for a in args:
        if "=" not in a:
            continue
        k, v = a.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.lower() in ("true", "false"):
            kw[k] = v.lower() == "true"
        else:
            try:
                kw[k] = int(v)
            except ValueError:
                try:
                    kw[k] = float(v)
                except ValueError:
                    kw[k] = v
    return kw


def _handle_command(orch: Orchestrator, line: str) -> bool:
    """返回 True 表示退出。"""
    parts = line.strip().split()
    cmd, args = parts[0], parts[1:]

    if cmd in ("/quit", "/exit", "/q"):
        return True

    if cmd == "/help":
        print(HELP_TEXT)
        return False

    if cmd == "/list":
        from skills.registry import list_skills, get_meta
        for name in list_skills():
            m = get_meta(name)
            print(f"  {name:25s} {m.source:6s} kw={len(m.keywords):2d}")
        return False

    if cmd == "/status":
        print(f"  {orch.get_status()}")
        return False

    if cmd == "/cancel":
        orch.cancel()
        return False

    if cmd == "/clear":
        if orch.memory:
            orch.memory.clear()
        print("  ✅ 对话历史已清空")
        return False

    if cmd == "/schema":
        if not args:
            print("  ❌ 用法: /schema <skill_name>")
            return False
        from skills.registry import get_meta
        m = get_meta(args[0])
        if m is None:
            print(f"  ❌ 未知 skill: {args[0]}")
            return False
        print(f"  name:     {m.name}")
        print(f"  class:    {m.class_path}")
        print(f"  category: {m.category}")
        print(f"  outputs:  {m.outputs}")
        print(f"  keywords: {m.keywords}")
        if m.kwargs_builder:
            try:
                default = m.kwargs_builder({"prompt": "", "original_text": ""}) or {}
                print(f"  defaults: {default}")
            except Exception as e:
                print(f"  defaults: <无法推断: {e}>")
        else:
            print("  defaults: (无 kwargs_builder)")
        return False
        
    if cmd == "/skill":
        if not args:
            print("  ❌ 用法: /skill <name> [k=v ...]")
            return False
        name = args[0]
        kwargs = _parse_kwargs(args[1:])
        print(f"  🚀 执行 skill: {name} kwargs={kwargs}")
        orch.run_skill(name, **kwargs)
        return False

    print(f"  ❌ 未知命令: {cmd}（/help 查看帮助）")
    return False


# ============================================================
# 主循环
# ============================================================

def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    bus = EventBus()
    ctx = AppContext.headless(settings, bus=bus)
    orch = Orchestrator(bus, ctx)
    ConsoleRenderer(bus)

    print(self_banner(orch))

    while True:
        try:
            raw = input("\033[1m> \033[0m")
            # 容忍复制粘贴时带上的 "> " 前缀
            line = raw.strip()
            while line.startswith(">"):
                line = line[1:].strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见")
            break

        if not line:
            continue

        if line.startswith("/"):
            if _handle_command(orch, line):
                print("👋 再见")
                break
            continue

        # 普通输入 → 走意图
        print(f"\033[36m[user]\033[0m {line}")
        try:
            orch.handle_text(line)
        except Exception as e:
            print(f"\033[31m[error]\033[0m {e}")

        print()


def self_banner(orch: Orchestrator) -> str:
    s = orch.settings
    mode = getattr(s, "generation_mode", "api")
    provider = getattr(s, "api_provider", "?")
    return (
        f"\n╭─ PromptForge CLI ─────────────────────╮\n"
        f"│ mode={mode:<6s} provider={provider:<12s}    │\n"
        f"│ /help 查看命令 · /quit 退出              │\n"
        f"╰────────────────────────────────────────╯"
    )


if __name__ == "__main__":
    main()