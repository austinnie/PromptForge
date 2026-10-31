# scripts/test_orchestrator.py
"""Orchestrator 独立验证（headless、不调 API）。"""

import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from application.events import EventBus
from application.context import AppContext
from application.orchestrator import Orchestrator
from config.settings import settings


def main():
    logging.basicConfig(
        level=logging.WARNING,  # 抑制 info 噪音
        format="%(levelname)s %(name)s: %(message)s",
    )

    bus = EventBus()
    ctx = AppContext.headless(settings, bus=bus)
    orch = Orchestrator(bus, ctx)

    # 所有事件打到 stdout
    bus.on("*", lambda e: print(f"  [{e.type}] {e.payload}"))

    print("\n=== T1: chat 意图（不触发 API）===")
    orch.handle_text("你好")
    print(f"  busy after: {orch.busy}")

    print("\n=== T2: 意图分发矩阵（只用 IntentAnalyzer，不实际执行）===")
    test_cases = [
        ("画一只猫", "text_to_image"),
        ("github日报", "skill"),
        ("生成视频：海边日落", "video"),
        ("你好吗", "chat"),
    ]
    for text, expected in test_cases:
        result = orch.intent.analyze(text)
        mark = "✓" if result.type == expected else "✗"
        print(f"  {mark} '{text}' -> {result.type}  (期望 {expected})")

    print("\n=== T3: registry 关键词与意图串通 ===")
    from skills.registry import find_by_keyword
    for text in ["github日报", "今日新闻", "生成音乐", "播放视频"]:
        hit = find_by_keyword(text)
        print(f"  '{text}' -> {hit}")

    print("\n=== T4: 状态查询 ===")
    print(f"  {orch.get_status()}")

    print("\n=== T5: 并发保护（第二次 handle_text 应被拒）===")
    import threading
    busy_flag = [True]

    def slow_analyze(*a, **kw):
        # 手动模拟 busy 状态
        return orch.intent.__class__().analyze(a[0])

    orch._busy = True
    orch.handle_text("再来一条")
    orch._busy = False

    print("\n✅ Orchestrator 冒烟测试完成")


if __name__ == "__main__":
    main()