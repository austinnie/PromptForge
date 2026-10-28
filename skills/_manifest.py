# skills/_manifest.py
"""Skill Manifest 加载器。

用途：
  - GUI 从 manifest 自动生成菜单
  - SkillHandler 从 manifest 解析 class（与 SKILL_ROUTES 二选一）
  - 未来的 SkillChain 从 manifest 读取依赖关系

设计：
  - 扫描 skills/*/meta.json，按 name 索引
  - 缓存到进程内（skill 数量少，meta 不变，无需热更新）
  - ★ 兼容两种 class 写法：
      短名   "skills.DailyPipeline"        -> 依赖 __init__.py 手动 re-export
      全路径 "skills.daily_pipeline.skill.DailyPipeline" -> 动态 import，零改动
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 允许通过环境变量覆盖（App / PyInstaller 打包时用）
SKILLS_DIR = Path(os.environ.get("PROMPTFORGE_SKILLS_DIR", Path(__file__).parent))

_MANIFEST_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

# meta.json 必填字段（用于早期校验）
REQUIRED_FIELDS = ("name", "class", "display_name")
# meta.json 字段类型（用于早期校验）
FIELD_TYPES = {
    "name": str,
    "class": str,
    "display_name": str,
    "description": str,
    "triggers": (list, str),
    "routes": (list, dict),
    "entry": str,
}


def _validate_manifest(name: str, data: Dict[str, Any], src: Path) -> List[str]:
    """返回警告列表（不抛异常，让 loader 决定怎么处理）。"""
    warns = []
    for k in REQUIRED_FIELDS:
        if k not in data:
            warns.append(f"{src}: 缺必填字段 '{k}'")
    for k, expected in FIELD_TYPES.items():
        if k in data and not isinstance(data[k], expected):
            warns.append(f"{src}: 字段 '{k}' 类型应为 {expected}, 实际 {type(data[k])}")
    return warns


def load_all_manifests(force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
    """扫描所有 skills/*/meta.json，返回 {name: manifest}。"""
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None and not force_reload:
        return _MANIFEST_CACHE

    result: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for meta_file in sorted(SKILLS_DIR.glob("*/meta.json")):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"⚠️ 解析 {meta_file} 失败: {e}")
            errors.append(f"{meta_file}: {e}")
            continue

        name = data.get("name")
        cls_path = data.get("class")
        if not name or not cls_path:
            logger.debug(f"⏭️ 跳过 {meta_file}（缺 name 或 class）")
            continue

        # ★ 字段校验（警告，不阻断）
        for w in _validate_manifest(name, data, meta_file):
            logger.warning(f"⚠️ {w}")
            errors.append(w)

        # ★ 重复 name 检测（后者覆盖前者，但明确记录）
        if name in result:
            logger.warning(f"⚠️ 重复 skill name: {name}，来自 {meta_file} 覆盖之前的")
            errors.append(f"重复 skill name: {name}")

        result[name] = data

    _MANIFEST_CACHE = result
    logger.info(f"✅ 加载 {len(result)} 个 skill manifest"
                + (f"（{len(errors)} 条警告）" if errors else ""))
    return result


def resolve_class(manifest: Dict[str, Any]):
    """'a.b.C' → ('a.b', 'C')"""
    cls_path = manifest.get("class", "")
    if "." not in cls_path:
        raise ValueError(f"invalid class path: {cls_path}")
    module_path, class_name = cls_path.rsplit(".", 1)
    return module_path, class_name


def import_skill_class(manifest: Dict[str, Any]):
    """★ 兼容两种 class 写法：
       1) 全路径 "skills.xxx.skill.Yyy"      -> 直接 import_module
       2) 短名   "skills.Yyy"                -> 先试 import_module('skills') + getattr
                                              -> 失败则 fallback: import skills.<name>.skill
    """
    module_path, class_name = resolve_class(manifest)

    # 尝试 A：作为完整模块路径 import
    try:
        module = importlib.import_module(module_path)
        if hasattr(module, class_name):
            return getattr(module, class_name)
    except ImportError:
        pass

    # 尝试 B：短名场景，走 skills.__init__ 的 re-export
    if module_path == "skills":
        skills_pkg = importlib.import_module("skills")
        if hasattr(skills_pkg, class_name):
            return getattr(skills_pkg, class_name)

    # 尝试 C：约定式 fallback（skills.<name>.skill.<Class>）
    skill_name = manifest.get("name", "")
    candidate = f"skills.{skill_name}.skill"
    try:
        module = importlib.import_module(candidate)
        if hasattr(module, class_name):
            return getattr(module, class_name)
    except ImportError:
        pass

    raise ImportError(
        f"无法解析 skill class: {manifest.get('class')} "
        f"(尝试模块: {module_path}, skills, {candidate})"
    )


def get_manifest(skill_name: str) -> Optional[Dict[str, Any]]:
    return load_all_manifests().get(skill_name)


def reload_manifests():
    """测试/调试用：强制清空缓存。"""
    global _MANIFEST_CACHE
    _MANIFEST_CACHE = None