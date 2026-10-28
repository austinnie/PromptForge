#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gather_code.py (PromptForge 优化版)
把项目源码合并为一个 txt，方便喂给 AI / 做代码备份。

用法:
    python gather_code.py                 # 默认输出 project_code_dump.txt
    python gather_code.py -o code.txt     # 自定义输出名
    python gather_code.py --max-size 256  # 单文件大小上限（KB），默认 512
"""
import argparse
import os
from pathlib import Path

# ==================== 配置区 ====================

# ---- 要收集的文件后缀（小写）----
INCLUDE_EXTS = {
    '.py', '.txt', '.json', '.env', '.md', '.yml', '.yaml',
    '.cfg', '.conf', '.xml', '.html', '.css', '.js',
    '.toml', '.ini', '.sh', '.bat', '.ps1', '.cmd',
    '.gitignore', '.dockerignore', '.editorconfig',
}

# ---- 即使白名单里有，也强制跳过的后缀 ----
EXCLUDE_EXTS = {
    # 图片/音视频
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico', '.svg',
    '.mp3', '.wav', '.mp4', '.mov', '.avi', '.mkv', '.mid',
    # 大体积二进制/模型
    '.sf2', '.exe', '.dll', '.so', '.pyd', '.pyc', '.pyo', '.pkl',
    # 数据库/日志/压缩包
    '.sqlite', '.db', '.log', '.zip', '.rar', '.7z', '.tar', '.gz',
    # 办公文档
    '.docx', '.doc', '.xlsx', '.pdf',
}

# ---- 仅在项目根目录第一层排除的目录（整棵剪枝）----
EXCLUDE_TOP_DIRS = {
    'output',        # 全是生成的文章、图片、临时文件
    'build',         # 打包生成物
    'dist',          # 打包生成物
    'img_cache',     # 图片缓存
    'assets',        # 主要是二维码、水印等图片，没必要收集
}

# ---- 任意层级都排除的目录名（整棵剪枝）----
EXCLUDE_DIR_NAMES = {
    '__pycache__', '.git', '.venv', 'venv', 'env',
    'node_modules', '.idea', '.vscode',
    'cookies',       # 极度敏感：社交平台的登录 Cookie
    'logs',          # 日志文件
    'soundfonts',    # skills/music_generator 下的音色库和 fluidsynth 运行文件
    'social_auto_upload.egg-info',
}

# ---- 明确不收集的敏感/无用文件名 ----
EXCLUDE_FILES = {
    '.env',
    '.env.backup',
    '.wechat_state.json',   # 微信后台登录凭据
    '.gitkeep',
    'list.txt',             # 目录结构清单
    'test_video.json',      # 测试数据
    'test_video.py',        # 测试脚本
    'video_test.log',
    'scan_blobs.py',        # 无关脚本
}

# ---- 其它配置 ----
OUTPUT_FILE = 'project_code_dump.txt'
DEFAULT_MAX_KB = 512          # 单文件大小上限 (512KB)
BINARY_SNIFF_BYTES = 8192     # 二进制嗅探前多少字节

# ==================== 核心逻辑 ====================

def is_binary(path: Path) -> bool:
    """粗判二进制：前 N 字节含 \\x00 即视为二进制"""
    try:
        with open(path, 'rb') as f:
            return b'\x00' in f.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True


def gather_files(root_dir: Path, output_name: str, max_bytes: int):
    files = []
    stats = {'ext': 0, 'name': 0, 'size': 0, 'binary': 0, 'dir': 0}

    for current_dir, dirs, filenames in os.walk(root_dir):
        cur = Path(current_dir)
        is_top = cur == root_dir

        # ① 目录剪枝（遇到不想要的目录直接跳过，不进入遍历，极快）
        kept_dirs = []
        for d in dirs:
            if d in EXCLUDE_DIR_NAMES:
                stats['dir'] += 1
                continue
            if is_top and d in EXCLUDE_TOP_DIRS:
                stats['dir'] += 1
                continue
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        # ② 文件过滤
        for name in filenames:
            p = cur / name

            # 黑名单文件名 / 输出文件自身
            if name in EXCLUDE_FILES or name == output_name:
                stats['name'] += 1
                continue

            suffix = p.suffix.lower()

            # 后缀黑名单优先
            if suffix in EXCLUDE_EXTS:
                stats['ext'] += 1
                continue

            # 白名单过滤
            if not (suffix in INCLUDE_EXTS or (not suffix and name.startswith('.'))):
                continue

            # 大小上限
            try:
                if p.stat().st_size > max_bytes:
                    stats['size'] += 1
                    continue
            except OSError:
                continue

            # 二进制嗅探（防止有些奇怪后缀的文件混进来）
            if is_binary(p):
                stats['binary'] += 1
                continue

            files.append(p)

    return sorted(files), stats


def main():
    ap = argparse.ArgumentParser(description='汇总 PromptForge 项目代码到单个 txt 文件')
    ap.add_argument('-o', '--output', default=OUTPUT_FILE, help='输出文件名')
    ap.add_argument('--max-size', type=int, default=DEFAULT_MAX_KB,
                    metavar='KB', help=f'单文件大小上限（KB），默认 {DEFAULT_MAX_KB}')
    args = ap.parse_args()

    root = Path.cwd()
    output_path = root / Path(args.output).name
    max_bytes = args.max_size * 1024

    print(f'📂 扫描目录: {root}')
    print(f'   剪枝顶层目录: {", ".join(sorted(EXCLUDE_TOP_DIRS))}')
    print(f'   剪枝任意目录: {", ".join(sorted(EXCLUDE_DIR_NAMES))}')

    files, stats = gather_files(root, output_path.name, max_bytes)
    if not files:
        print('⚠️  未找到符合条件的文件，请检查配置。')
        return

    print(f'📄 命中 {len(files)} 个文件，正在写入 {output_path.name} ...')

    with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
        f.write(f'项目代码汇总 (扫描于 {root})\n')
        f.write(f'包含文件数: {len(files)}\n')
        f.write('=' * 80 + '\n\n')

        for p in files:
            rel = p.relative_to(root)
            f.write(f'=== 文件: {rel.as_posix()} ===\n')
            try:
                content = p.read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                content = f'[读取失败: {e}]'
            f.write(content)
            if not content.endswith('\n'):
                f.write('\n')
            f.write('\n' + '-' * 40 + '\n\n')

    size_kb = output_path.stat().st_size // 1024
    print(f'✅ 完成: {output_path.name}  ({size_kb} KB, {len(files)} 个文件)')
    print(f'   跳过统计: 后缀黑名单 {stats["ext"]} · 文件名 {stats["name"]} · 目录 {stats["dir"]} · '
          f'超 {args.max_size}KB {stats["size"]} · 二进制 {stats["binary"]}')


if __name__ == '__main__':
    main()