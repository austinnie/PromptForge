#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gather_code.py (PromptForge 架构版)

把项目源码按"架构层级 + 重要度"合并成一个 txt，方便在一个会话里
和 AI 讨论整体架构、做重构。

与旧版的区别：
  1. 不按路径字母序，而是按 T0~T6 分层
  2. 大文件支持 skeleton 模式（只留签名+docstring）
  3. 明确剔除 presets/、themes/、layers/、output/ 等噪音
  4. 输出头部带"文件索引表"，AI 可以据此按需读取

用法:
    python gather_code.py                      # 默认输出 project_code_dump.txt
    python gather_code.py -o arch.txt          # 自定义输出
    python gather_code.py --list               # 只打印索引，不写文件
    python gather_code.py --tier T0,T1         # 只收某几层
    python gather_code.py --skeleton-lines 40  # skeleton 模式保留前 N 行（默认 60）
"""
import argparse
import ast
import os
import re
from pathlib import Path
from typing import Iterable

# ============================================================
# 1. 收录策略表
# ============================================================

# ---- 每层收录哪些文件（相对路径，posix 格式）----
# 值 = ("full" | "skeleton" | "auto", 备注)
TIER_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "T0 入口/配置": {
        "main.py":               ("full", "启动入口"),
        "config/__init__.py":    ("full", "配置导出"),
        "config/settings.py":    ("full", "全局配置（含 provider 配置自动扫描）"),
        ".env.sample":           ("full", "环境变量模板"),
        "requirements.txt":      ("full", "依赖清单"),
        "presets_meta.py":       ("skeleton", "预设元数据（100+ 条，只留结构）"),
        "preset_bridge.py":      ("full", "LayerForge 桥接"),
    },

    "T1 编排核心": {
        "core/__init__.py":        ("full", "core 导出"),
        "core/intent_analyzer.py": ("full", "意图分析（全类型路由）"),
        "core/skill_routes.py":    ("full", "skill 触发词表"),
        "core/backend.py":         ("full", "本地/API 后端抽象"),
        "core/llm_client.py":      ("full", "统一 LLM 客户端（Agnes+Ollama）"),
        "core/composer.py":        ("full", "6 层提示词组合"),
        "core/safety.py":          ("skeleton", "安全词库（只留类结构）"),
        "core/context_manager.py": ("full", "上下文管理"),
        "core/prompt_builder.py":  ("full", "提示词构建"),
        "core/loader.py":          ("full", "layer 动态加载"),
    },

    "T2 Provider 抽象层": {
        "providers/__init__.py": ("full", "providers 导出 + 自动扫描"),
        "providers/base.py":     ("full", "统一请求对象 + Protocol"),
        "providers/registry.py": ("full", "注册表"),
        "providers/fallback.py": ("full", "回退封装"),
        "providers/errors.py":   ("full", "异常体系"),
    },

    "T3 Provider 适配器": {
        "providers/adapters/agnes.py":       ("full", "Agnes adapter（范式样板）"),
        "providers/adapters/pollinations.py":("full", "Pollinations adapter（匿名/带 key 双路径）"),
        # _impl 只留骨架：这两个是 1000 行大文件，adapter 已封装
        "providers/_impl/agnes.py":       ("skeleton", "Agnes engine 实现（1000+ 行）"),
        "providers/_impl/pollinations.py":("skeleton", "Pollinations engine 实现（1000+ 行）"),
    },

    "T4 Handlers": {
        "handlers/__init__.py":         ("full", "handler 导出"),
        "handlers/base.py":             ("full", "handler 基类"),
        "handlers/text_to_image.py":    ("full", "文生图（走 backend）"),
        "handlers/image_to_image.py":   ("full", "图生图"),
        "handlers/skill_handler.py":    ("full", "skill 调度（importlib 动态加载）"),
        "handlers/preset_handler.py":   ("skeleton", "预设处理（大文件）"),
        "handlers/video_handler.py":    ("skeleton", "视频处理"),
        "handlers/multi_person_handler.py": ("skeleton", "多人合成"),
        "handlers/couple_handler.py":   ("skeleton", "双人合成"),
        "handlers/chat_handler.py":     ("skeleton", "对话处理"),
    },

    "T5 Skills 骨架": {
        "skills/__init__.py":          ("full", "skills 导出"),
        "skills/_provider_helper.py":  ("full", "skills 层 provider 构造器"),
        "skills/image_generator/skill.py":  ("full", "图像生成（走 FallbackImageProvider）"),
        "skills/video_generator/skill.py":  ("full", "视频生成"),
        "skills/image_curator/skill.py":    ("skeleton", "图片鉴赏"),
        "skills/wechat_formatter/skill.py": ("full", "微信排版（含 publish 接口）"),
        "skills/daily_pipeline/skill.py":   ("skeleton", "每日管线"),
        "skills/github_repo_daily/skill.py":("skeleton", "GitHub 日报（走 LLMClient）"),
        "skills/news_aggregator/skill.py":  ("skeleton", "新闻聚合（走 LLMClient）"),
        "skills/novel_writer/skill.py":     ("skeleton", "小说生成（走 LLMClient）"),
        "skills/tech_hot_article/skill.py": ("skeleton", "技术文章"),
        "skills/music_generator/skill.py":  ("skeleton", "音乐生成"),
        "skills/voice_assistant/skill.py":  ("skeleton", "语音合成"),
        "skills/search_engine/skill.py":    ("skeleton", "匿名搜索"),
        "skills/video_player/skill.py":     ("skeleton", "视频播放"),
        "skills/music_player/skill.py":     ("skeleton", "音乐播放"),
        "skills/radio_player/skill.py":     ("skeleton", "广播播放"),
        "skills/video_sniffer/skill.py":    ("skeleton", "视频嗅探"),
        "skills/social_auto_upload/skill.py":("skeleton", "多平台分发"),
    },

    "T6 薄壳 / 外围": {
        "gui/__init__.py":          ("full", "GUI 导出"),
        "gui/app.py":               ("skeleton", "Tkinter 主界面（3000+ 行，只留结构）"),
        "multimedia/__init__.py":   ("full", "多媒体导出"),
        "multimedia/workflow.py":   ("skeleton", "多媒体编排"),
        "multimedia/assembler.py":  ("skeleton", "视频合成"),
        "multimedia/subtitle.py":   ("skeleton", "字幕生成"),
        "services/__init__.py":     ("full", "services 导出"),
        "services/llm_service.py":  ("skeleton", "Ollama 服务（旧接口）"),
        "services/pipeline_pool.py":("skeleton", "Pipeline 池"),
        "services/image_processor.py": ("skeleton", "图片后处理"),
        "scripts/daily_task.py":    ("skeleton", "每日任务 CLI"),
        "scripts/github_daily_task.py": ("skeleton", "GitHub 日报 CLI"),
        "scripts/weekly_tech_task.py":  ("skeleton", "每周技术任务"),
        "scripts/multi_publish.py": ("skeleton", "多平台发布"),
    },
}

# ---- 整目录剪枝（任意层级）----
HARD_EXCLUDE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env",
    "node_modules", ".idea", ".vscode",
    "output",          # 生成产物
    "assets",          # 二维码/水印
    "cookies",         # 敏感
    "logs",            # 日志
    "soundfonts",      # 音色库
    "static",          # 静态图
    "videos",          # 测试视频
    "images",          # 生成图
    "word",            # word 输出
    "articles",        # 文章输出
    "novels",          # 小说输出
    "social_auto_upload.egg-info",
}

# ---- 即使出现在 TIER_MAP 里也不展开的子项 ----
# 这些是"词库/配置"型文件，只在索引里留名字
CONFIG_ONLY = {
    "presets",            # 100+ 风格预设
    "themes",             # 33 个主题 JSON
    "layers",             # 6 层词库
    "templates",          # HTML 模板
}

# ============================================================
# 2. 工具函数
# ============================================================

_BINARY_SNIFF = 8192


def is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(_BINARY_SNIFF)
    except OSError:
        return True


def _docstring_first_line(node: ast.AST) -> str:
    """取 def/class 的 docstring 首行"""
    ds = ast.get_docstring(node)
    if not ds:
        return ""
    return ds.strip().splitlines()[0].strip()


def skeletonize(code: str, max_lines: int = 60) -> str:
    """
    把 Python 文件精简为骨架：
      - 保留文件级 docstring 前 3 行
      - 保留所有 import
      - 保留所有 class/def 签名 + docstring 首行
      - 保留模块级赋值（如 __all__、常量）的第一行
      - 其余函数体/类体全部折叠为 "..."
      - 若解析失败，退回"保留前 N 行"

    注意：只在 max_lines 不够用时才真折叠；如果文件本来就短（< max_lines），
    直接返回原文，避免把已经很小的重要文件骨架化。
    """
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return code

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # 语法错误就只截断
        return "\n".join(lines[:max_lines]) + f"\n# ... [truncated, {len(lines)} lines]"

    out: list[str] = []
    out.append(f"# [SKELETON] 原文件 {len(lines)} 行，以下仅保留结构")

    # 文件级 docstring
    doc = ast.get_docstring(tree)
    if doc:
        for i, l in enumerate(doc.strip().splitlines()[:3]):
            out.append(f'""" {l}' if i == 0 else f"    {l}")
        if doc.strip().splitlines()[:3]:
            out.append('"""')
        out.append("")

    def emit_node(node: ast.AST, indent: int = 0):
        pad = "    " * indent
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            header = f"{pad}class {node.name}"
            if bases:
                header += f"({bases})"
            header += ":"
            out.append(header)
            d = _docstring_first_line(node)
            if d:
                out.append(f'{pad}    """{d}"""')
            # 类内成员
            body_emitted = False
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    emit_node(child, indent + 1)
                    body_emitted = True
                elif isinstance(child, ast.Assign):
                    out.append(f"{pad}    {ast.unparse(child)}")
                    body_emitted = True
            if not body_emitted:
                out.append(f"{pad}    ...")
            out.append("")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args = ast.unparse(node.args)
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            out.append(f"{pad}{kind} {node.name}({args}){ret}:")
            d = _docstring_first_line(node)
            if d:
                out.append(f'{pad}    """{d}"""')
            out.append(f"{pad}    ...")
            out.append("")

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append(ast.unparse(node))
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            emit_node(node, 0)
        elif isinstance(node, ast.Assign):
            # 只收 __all__、大写常量、简单赋值
            target = ast.unparse(node.targets[0]) if node.targets else ""
            if target in ("__all__",) or target.isupper() or target.isidentifier():
                line = ast.unparse(node)
                if len(line) > 120:
                    line = line[:117] + "..."
                out.append(line)

    return "\n".join(out)


# ============================================================
# 3. 收录引擎
# ============================================================

def _find_file(root: Path, rel: str) -> Path | None:
    p = root / rel
    return p if p.exists() and p.is_file() else None


def gather(
    root: Path,
    output_name: str,
    tiers: Iterable[str] | None = None,
    skeleton_lines: int = 60,
) -> tuple[list[tuple[str, str, str, str]], dict]:
    """
    返回 (items, stats)
    item = (tier, rel_path, mode, content)
    """
    items: list[tuple[str, str, str, str]] = []
    stats = {"full": 0, "skeleton": 0, "missing": 0, "skipped_big": 0}

    selected_tiers = list(TIER_MAP.keys()) if not tiers else list(tiers)

    for tier in selected_tiers:
        if tier not in TIER_MAP:
            continue
        mapping = TIER_MAP[tier]
        for rel, (mode, _note) in mapping.items():
            p = _find_file(root, rel)
            if p is None:
                stats["missing"] += 1
                continue

            # 全局排除目录复查（防止 TIER_MAP 里手滑写错）
            if any(part in HARD_EXCLUDE_DIRS for part in p.parts):
                continue

            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                items.append((tier, rel, "error", f"[读取失败: {e}]"))
                continue

            if is_binary(p):
                stats["skipped_big"] += 1
                continue

            if mode == "full":
                content = raw
                stats["full"] += 1
            elif mode == "skeleton":
                content = skeletonize(raw, max_lines=skeleton_lines)
                stats["skeleton"] += 1
            else:  # auto
                content = skeletonize(raw, max_lines=skeleton_lines) if len(raw.splitlines()) > skeleton_lines else raw
                stats["full" if content == raw else "skeleton"] += 1

            items.append((tier, rel, mode, content))

    return items, stats


def _list_config_dirs(root: Path) -> dict[str, list[str]]:
    """只列出名字，不读内容：presets/themes/layers/templates"""
    out: dict[str, list[str]] = {}
    for d in CONFIG_ONLY:
        p = root / d
        if p.exists() and p.is_dir():
            names = sorted(
                f.name for f in p.iterdir()
                if f.is_file() and not f.name.startswith("_")
            )
            out[f"{d}/"] = names
    return out


# ============================================================
# 4. 主流程
# ============================================================

def main():
    ap = argparse.ArgumentParser(
        description="PromptForge 架构版代码汇总",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-o", "--output", default="project_code_dump.txt")
    ap.add_argument("--tier", default=None,
                    help="只收录指定层，逗号分隔，如 T0,T1,T2（默认全部）")
    ap.add_argument("--skeleton-lines", type=int, default=60,
                    help="skeleton 模式保留前 N 行（默认 60）")
    ap.add_argument("--list", action="store_true",
                    help="只打印索引，不写文件")
    args = ap.parse_args()

    root = Path.cwd()
    tiers = [t.strip() for t in args.tier.split(",")] if args.tier else None

    items, stats = gather(root, args.output, tiers, args.skeleton_lines)
    config_dirs = _list_config_dirs(root)

    # ---- 索引 ----
    print("=" * 70)
    print(f"  PromptForge 架构汇总 · 扫描于 {root}")
    print("=" * 70)
    for tier in (tiers or TIER_MAP.keys()):
        tier_items = [it for it in items if it[0] == tier]
        if not tier_items:
            continue
        print(f"\n【{tier}】({len(tier_items)} 个文件)")
        for _t, rel, mode, content in tier_items:
            size = len(content)
            flag = {"full": "  ", "skeleton": "◐ ", "error": "✗ "}.get(mode, "  ")
            print(f"  {flag}{rel:<48s} {size:>7d} chars")

    if config_dirs:
        print("\n【配置目录（仅索引，不展开）】")
        for d, names in config_dirs.items():
            print(f"  {d:<16s} {len(names)} 项  ({', '.join(names[:4])}{'...' if len(names) > 4 else ''})")

    print(f"\n统计: full={stats['full']} skeleton={stats['skeleton']} "
          f"missing={stats['missing']} skipped={stats['skipped_big']}")

    if args.list:
        return

    # ---- 写入 ----
    output_path = root / Path(args.output).name
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"PromptForge 架构代码汇总 (扫描于 {root})\n")
        f.write(f"收录文件: {len(items)} · full={stats['full']} · skeleton={stats['skeleton']}\n")
        f.write("=" * 80 + "\n\n")

        # 文件索引表
        f.write("## 文件索引\n\n")
        for tier in (tiers or TIER_MAP.keys()):
            tier_items = [it for it in items if it[0] == tier]
            if not tier_items:
                continue
            f.write(f"### {tier}\n")
            for _t, rel, mode, _c in tier_items:
                tag = {"full": "", "skeleton": " [骨架]", "error": " [错误]"}.get(mode, "")
                f.write(f"- `{rel}`{tag}\n")
            f.write("\n")

        if config_dirs:
            f.write("### 配置目录（仅索引）\n")
            for d, names in config_dirs.items():
                f.write(f"- `{d}`: {len(names)} 项\n")
            f.write("\n")

        f.write("\n" + "=" * 80 + "\n\n")

        # 正文
        for tier in (tiers or TIER_MAP.keys()):
            tier_items = [it for it in items if it[0] == tier]
            if not tier_items:
                continue
            f.write("#" * 80 + "\n")
            f.write(f"# {tier}\n")
            f.write("#" * 80 + "\n\n")
            for _t, rel, mode, content in tier_items:
                f.write("=" * 76 + "\n")
                f.write(f"=== 文件: {rel}  [{mode}] ===\n")
                f.write("=" * 76 + "\n")
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n\n")

    size_kb = output_path.stat().st_size // 1024
    print(f"\n✅ 已写入: {output_path.name}  ({size_kb} KB)")


if __name__ == "__main__":
    main()