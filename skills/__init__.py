# skills/__init__.py
"""技能模块 - 可插拔功能

★ 懒加载设计：
  - 不在 import 时拉起所有 skill（避免 ollama/fluidsynth/playwright 等重依赖拖慢启动）
  - 通过 __getattr__ 按需加载，meta.json 是唯一契约
  - 删除所有手工 re-export，新增 skill 零改动
"""

from __future__ import annotations

import importlib
from typing import Any

from ._manifest import load_all_manifests, import_skill_class


def __getattr__(name: str) -> Any:
    """PEP 562：模块级 __getattr__，按需解析 skill class。

    访问 skills.DailyPipeline 时：
      - 从 manifest 找到 name == DailyPipeline 的 skill
      - 动态 import 并返回 class
    """
    manifests = load_all_manifests()

    # 1) 精确命中 skill name
    if name in manifests:
        return import_skill_class(manifests[name])

    # 2) 遍历所有 manifest，看有没有 class 名 == name 的（兼容短名调用）
    for m in manifests.values():
        cls_path = m.get("class", "")
        if cls_path.rsplit(".", 1)[-1] == name:
            return import_skill_class(m)

    raise AttributeError(f"module 'skills' has no attribute '{name}'")


def __dir__():
    """让 dir(skills) 和 IDE 补全能看到所有 skill。"""
    return sorted(
        set(list(globals().keys()))
        | {m.get("class", "").rsplit(".", 1)[-1] for m in load_all_manifests().values()}
    )


__all__ = [
    # 只导出通用 API，具体 skill 由 __getattr__ 懒加载
    "load_all_manifests",
    "import_skill_class",
]