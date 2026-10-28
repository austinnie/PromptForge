# skills/_manifest.py
"""Skill Manifest 加载器。

用途：
  - GUI 从 manifest 自动生成菜单
  - SkillHandler 从 manifest 解析 class（可选，与 SKILL_ROUTES 二选一）
  - 未来的 SkillChain 从 manifest 读取依赖关系

设计：
  - 扫描 skills/*/meta.json，按 name 索引
  - 缓存到进程内（skill 数量少，meta 不变，无需热更新）
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent
_MANIFEST_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def load_all_manifests(force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
    """扫描所有 skills/*/meta.json，返回 {name: manifest}。

    容错：
      - 缺 name / class 的 manifest 直接跳过
      - JSON 解析失败只警告，不抛异常
    """
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None and not force_reload:
        return _MANIFEST_CACHE

    result: Dict[str, Dict[str, Any]] = {}
    for meta_file in sorted(SKILLS_DIR.glob("*/meta.json")):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"⚠️ 解析 {meta_file} 失败: {e}")
            continue

        name = data.get("name")
        cls_path = data.get("class")
        if not name or not cls_path:
            logger.debug(f"⏭️ 跳过 {meta_file}（缺 name 或 class）")
            continue

        result[name] = data

    _MANIFEST_CACHE = result
    logger.info(f"✅ 加载 {len(result)} 个 skill manifest")
    return result


def resolve_class(manifest: Dict[str, Any]):
    """'skills.image_curator.ImageCurator' → (module, class_name)"""
    cls_path = manifest.get("class", "")
    if "." not in cls_path:
        raise ValueError(f"invalid class path: {cls_path}")
    module_path, class_name = cls_path.rsplit(".", 1)
    return module_path, class_name


def import_skill_class(manifest: Dict[str, Any]):
    """从 manifest 动态 import skill 类。"""
    module_path, class_name = resolve_class(manifest)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_manifest(skill_name: str) -> Optional[Dict[str, Any]]:
    return load_all_manifests().get(skill_name)