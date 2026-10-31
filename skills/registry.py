# skills/registry.py
"""统一 Skill 注册表（阶段 1）。

合并两个数据源：
  1. skills/*/meta.json           ← skill 自描述（通过 skills._manifest 加载）
  2. core/skill_routes.SKILL_ROUTES ← 触发词 + handler 配置（旧版）

策略：
  - class 路径：meta 的 "class" 优先，缺失时用 routes 的 module + class 拼
  - keywords / system_hint / config_overrides / kwargs_builder：routes 优先
    （旧版这些都在 routes 里；未来会迁移到各 skill 的 meta.json）
  - 只在单侧存在的 skill：打 warning，仍可用

后续（阶段 2）：
  - 触发词迁移到 meta.json 后，本模块不再 import core.skill_routes
  - core/skill_routes.py 变成本模块的薄壳 re-export
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class SkillMeta:
    name: str
    class_path: str                       # 完整路径或短名
    keywords: list[str] = field(default_factory=list)
    system_hint: str = ""
    category: str = "general"
    outputs: tuple[str, ...] = ()
    config_overrides: dict = field(default_factory=dict)
    kwargs_builder: Optional[Callable] = None
    source: str = "meta"                  # "meta" / "routes" / "both"

    @property
    def module_path(self) -> str:
        return self.class_path.rsplit(".", 1)[0] if "." in self.class_path else "skills"

    @property
    def class_name(self) -> str:
        return self.class_path.rsplit(".", 1)[-1]


# ============================================================
# 数据加载
# ============================================================

def _load_from_meta() -> dict[str, dict]:
    """从 skills/*/meta.json 加载。"""
    try:
        from skills._manifest import load_all_manifests
        return load_all_manifests() or {}
    except Exception as e:
        logger.warning(f"⚠️ 加载 skills/*/meta.json 失败: {e}")
        return {}


def _load_from_routes() -> dict[str, dict]:
    """从 core/skill_routes.py 加载（阶段 1 临时依赖）。"""
    try:
        from core.skill_routes import SKILL_ROUTES
        return SKILL_ROUTES or {}
    except Exception as e:
        logger.warning(f"⚠️ 加载 core.skill_routes 失败: {e}")
        return {}


# ============================================================
# 构建注册表
# ============================================================

def _build_registry() -> dict[str, SkillMeta]:
    meta_map = _load_from_meta()
    routes_map = _load_from_routes()

    result: dict[str, SkillMeta] = {}
    all_names = set(meta_map) | set(routes_map)

    for name in all_names:
        meta = meta_map.get(name, {})
        route = routes_map.get(name, {})

        # ---- class 路径 ----
        class_path = meta.get("class", "")
        if not class_path:
            mod = route.get("module", "")
            cls = route.get("class", "")
            if mod and cls:
                # route 里 module="skills" class="ImageGenerator" 这种写法
                # 保留短名，靠 skills.__getattr__ 懒加载
                class_path = f"{mod}.{cls}" if mod != "skills" else cls
        if not class_path:
            logger.warning(f"⚠️ {name} 缺少 class 路径，跳过")
            continue

        # ---- 其它字段：routes 优先（阶段 1） ----
        keywords = route.get("keywords") or meta.get("keywords", [])
        system_hint = route.get("system_hint") or meta.get("system_hint", "")
        category = meta.get("category", "general")
        outputs = tuple(meta.get("outputs", ()))
        config_overrides = (
            route.get("config_overrides") or meta.get("config_overrides") or {}
        )
        kwargs_builder = (
            route.get("kwargs_builder") or meta.get("kwargs_builder")
        )

        # ---- 来源标记 ----
        # ---- 来源标记 ----
        if name in meta_map and name in routes_map:
            source = "both"
        elif name in meta_map:
            source = "meta"
            if not keywords:
                logger.info(
                    f"ℹ️ {name} 只在 meta.json 存在且无 keywords"
                    f"（不参与关键词触发，仅可被显式调用）"
                )
        else:
            source = "routes"
            if name == "local_model_manage":
                logger.info(
                    f"ℹ️ {name} 来自 skill_routes，class 指向 handlers/{meta.get('class', '?')}"
                )
            else:
                logger.warning(
                    f"⚠️ {name} 只在 skill_routes 存在，建议补 skills/{name}/meta.json"
                )

        result[name] = SkillMeta(
            name=name,
            class_path=class_path,
            keywords=keywords,
            system_hint=system_hint,
            category=category,
            outputs=outputs,
            config_overrides=config_overrides,
            kwargs_builder=kwargs_builder,
            source=source,
        )

    return result


_REGISTRY: Optional[dict[str, SkillMeta]] = None


def _registry() -> dict[str, SkillMeta]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
        logger.info(
            f"✅ Skill 注册表已加载: {len(_REGISTRY)} 个 "
            f"(both={sum(1 for m in _REGISTRY.values() if m.source == 'both')}, "
            f"routes={sum(1 for m in _REGISTRY.values() if m.source == 'routes')}, "
            f"meta={sum(1 for m in _REGISTRY.values() if m.source == 'meta')})"
        )
    return _REGISTRY


# ============================================================
# 公开 API
# ============================================================

def list_skills() -> list[str]:
    """返回所有已注册 skill 名。"""
    return sorted(_registry().keys())


def get_meta(name: str) -> Optional[SkillMeta]:
    """取单个 skill 的元数据。"""
    return _registry().get(name)


def all_meta() -> dict[str, SkillMeta]:
    """返回所有元数据副本。"""
    return dict(_registry())


def find_by_keyword(text: str) -> Optional[tuple[str, str]]:
    """按关键词匹配，返回 (skill_name, matched_keyword)。

    匹配规则与旧版一致：
      - 遍历所有 skill
      - 每个 skill 的 keywords 按长度倒序，避免短词先命中
    """
    tl = text.lower()
    for name, meta in _registry().items():
        for kw in sorted(meta.keywords, key=len, reverse=True):
            if kw and kw.lower() in tl:
                return name, kw
    return None


def list_by_category(category: Optional[str] = None) -> dict[str, list[SkillMeta]]:
    """按 category 分组。category=None 返回全部分组。"""
    grouped: dict[str, list[SkillMeta]] = {}
    for meta in _registry().values():
        if category and meta.category != category:
            continue
        grouped.setdefault(meta.category, []).append(meta)
    return grouped


def import_skill_class(meta: SkillMeta):
    """按 SkillMeta 导入 class。

    - class_path 有 "." → 走 importlib
    - class_path 是短名 → 走 skills.__getattr__（懒加载）
    """
    if "." in meta.class_path:
        mod = importlib.import_module(meta.module_path)
        return getattr(mod, meta.class_name)
    import skills
    return getattr(skills, meta.class_path)


def reload() -> None:
    """清空缓存，下次访问重新构建。"""
    global _REGISTRY
    _REGISTRY = None


# ============================================================
# 阶段 1 兼容：给 core/skill_routes.py 的旧结构视图
# ============================================================

def _legacy_routes_view() -> dict[str, dict]:
    """返回和旧 SKILL_ROUTES 结构一致的 dict（供过渡期）。

    阶段 2 完成后删除本函数。
    """
    out = {}
    for name, meta in _registry().items():
        # 反推出旧格式的 module / class
        if "." in meta.class_path:
            mod, cls = meta.module_path, meta.class_name
        else:
            mod, cls = "skills", meta.class_path

        out[name] = {
            "keywords": meta.keywords,
            "system_hint": meta.system_hint,
            "module": mod,
            "class": cls,
            "config_overrides": meta.config_overrides,
            "kwargs_builder": meta.kwargs_builder,
        }
    return out