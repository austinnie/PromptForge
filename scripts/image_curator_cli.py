#!/usr/bin/env python
"""
🖼️ 图片鉴赏文章生成 CLI

用法：
  python image_curator_cli.py output
  python image_curator_cli.py output --title "机甲之美" --open
  python image_curator_cli.py output --formats md,html,docx,pdf,clipboard
"""

import sys
import os
import argparse
from pathlib import Path

# ← 关键：项目根就是本文件所在目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.image_curator import ImageCurator


ALL_FORMATS = ["md", "html", "docx", "pdf", "clipboard"]


def _parse_formats(fmts: set[str]) -> list[str]:
    """CLI 格式集 → skill.write_formats 列表。"""
    out = {"md", "html"}
    for f in fmts:
        if f in ("docx", "pdf", "clipboard"):
            out.add(f)
    return list(out)


def main():
    parser = argparse.ArgumentParser(description="🖼️ 图片鉴赏文章生成")
    parser.add_argument("directory", help="图片目录")
    parser.add_argument("--title", "-t", help="文章标题（默认用时间）")
    parser.add_argument("--intro", help="引言（默认 AI 生成）")
    parser.add_argument("--recursive", "-r", action="store_true", help="递归子目录")
    parser.add_argument("--max-images", type=int, default=30, help="最多处理多少张")
    parser.add_argument(
        "--formats", "-f",
        default="md,html,docx,pdf",
        help="输出格式，逗号分隔。可选：md,html,docx,pdf,clipboard",
    )
    parser.add_argument("--open", action="store_true",
                        help="生成后打开（优先 html → docx → pdf）")
    args = parser.parse_args()

    fmts = {f.strip().lower() for f in args.formats.split(",") if f.strip()}
    unknown = fmts - set(ALL_FORMATS)
    if unknown:
        print(f"⚠️ 未知格式: {unknown}，可选: {ALL_FORMATS}")
        return

    print(f"\n🖼️  图片鉴赏: {args.directory}")
    print(f"   输出格式: {', '.join(sorted(fmts))}")

    curator = ImageCurator({
        "write_formats": _parse_formats(fmts),
    })

    result = curator.curate(
        args.directory,
        title=args.title,
        intro=args.intro,
        recursive=args.recursive,
        max_images=args.max_images,
    )

    if result["status"] != "success":
        print(f"\n❌ 生成失败: {result.get('error')}")
        return

    data = result["result"]
    print("\n✅ 完成！")
    print(f"   📝 Markdown : {data.get('article_md')}")
    if data.get("article_html"):
        print(f"   🌐 HTML     : {data['article_html']}")
    if data.get("article_docx"):
        print(f"   📘 Word     : {data['article_docx']}")
    if data.get("article_pdf"):
        print(f"   📄 PDF      : {data['article_pdf']}")
    if data.get("copied_to_clipboard"):
        print(f"   📋 剪贴板   : 已复制 Markdown 全文")
    print(f"   🖼️  图片     : {data.get('image_count')} 张")
    print(f"   ⏱️  耗时     : {data.get('elapsed')}")
    print(f"   📁 输出目录 : {data.get('output_dir')}")

    if args.open:
        for key in ("article_html", "article_docx", "article_pdf"):
            p = data.get(key)
            if p and Path(p).exists():
                try:
                    if sys.platform == "win32":
                        os.startfile(p)
                    elif sys.platform == "darwin":
                        import subprocess
                        subprocess.Popen(["open", p])
                    else:
                        import subprocess
                        subprocess.Popen(["xdg-open", p])
                    print(f"\n📂 已打开: {p}")
                except Exception as e:
                    print(f"⚠️ 打开失败: {e}")
                break


if __name__ == "__main__":
    main()