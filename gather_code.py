#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
获取当前项目所有代码文件，合并为一个 txt 文件
用法: python gather_code.py
输出: project_code_dump.txt (保存在当前目录)
"""

import os
import sys
from pathlib import Path

# ==================== 配置区 ====================
# 要包含的文件扩展名（小写）
INCLUDE_EXTS = {
    '.py', '.txt', '.json', '.env', '.md', '.yml', '.yaml',
    '.cfg', '.conf', '.xml', '.html', '.css', '.js', '.lora',
    '.model_config', '.gitignore', '.dockerignore', '.editorconfig'
}

# 要排除的目录名（完全匹配）
EXCLUDE_DIRS = {
    '__pycache__', '.git', '.venv', 'venv', 'env',
    'node_modules', '.idea', '.vscode', 'dist', 'build',
    '__pypackages__'
}

# 要排除的具体文件（完全匹配，如 .env 可能不想包含？但 .env 通常包含敏感信息，建议排除）
EXCLUDE_FILES = {
    '.env',       # 包含 API Key，不建议提交
    '.cache.json',
    'lora_config',
    '.model_config',
    # 可根据需要添加
}

# 输出文件名
OUTPUT_FILE = "project_code_dump.txt"

# ==================== 核心逻辑 ====================

def should_include_file(file_path: Path, root_dir: Path) -> bool:
    """判断是否应该包含该文件"""
    # 检查是否在排除目录中
    for parent in file_path.parents:
        if parent.name in EXCLUDE_DIRS:
            return False

    # 检查文件名是否在排除列表
    if file_path.name in EXCLUDE_FILES:
        return False

    # 检查扩展名是否在包含列表
    ext = file_path.suffix.lower()
    if ext in INCLUDE_EXTS:
        return True

    # 特别允许无扩展名的文件（如 .env.example 等）
    if not ext and file_path.name.startswith('.'):
        return True

    return False

def gather_files(root_dir: Path) -> list:
    """递归收集所有符合条件的文件路径"""
    files = []
    for item in root_dir.rglob('*'):
        if item.is_file() and should_include_file(item, root_dir):
            files.append(item)
    return sorted(files)  # 按路径排序

def main():
    root = Path.cwd()
    print(f"📂 扫描目录: {root}")

    files = gather_files(root)
    if not files:
        print("⚠️ 未找到任何符合条件的文件，请检查配置。")
        return

    print(f"📄 找到 {len(files)} 个文件，正在写入 {OUTPUT_FILE}...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8', errors='replace') as out_f:
        out_f.write(f"项目代码汇总 (扫描于 {root})\n")
        out_f.write(f"包含文件数: {len(files)}\n")
        out_f.write("=" * 80 + "\n\n")

        for file_path in files:
            rel_path = file_path.relative_to(root)
            out_f.write(f"=== 文件: {rel_path} ===\n")
            try:
                content = file_path.read_text(encoding='utf-8', errors='replace')
                out_f.write(content)
            except Exception as e:
                out_f.write(f"[读取失败: {e}]\n")
            out_f.write("\n\n" + "-" * 40 + "\n\n")  # 文件分隔符

    print(f"✅ 完成！输出文件: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) // 1024} KB)")

if __name__ == "__main__":
    main()