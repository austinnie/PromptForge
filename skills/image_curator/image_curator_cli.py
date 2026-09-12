#!/usr/bin/env python
"""
🖼️ 图片鉴赏文章生成 CLI

用法：
  python image_curator_cli.py output/机甲
  python image_curator_cli.py output/机甲 --title "机甲之美" --open
  python image_curator_cli.py output/机甲 --formats md,docx,pdf,clipboard
"""

import sys
import os
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.image_curator import ImageCurator


ALL_FORMATS = ["md", "html", "docx", "pdf", "clipboard"]


def main():
    parser = argparse.ArgumentParser(description="🖼️ 图片鉴赏文章生成")
    parser.add_argument("directory", help="图片目录")
    parser.add_argument("--title", "-t", help="文章标题（默认用目录名）")
    parser.add_argument("--intro", help="引言（默认 AI 生成）")
    parser.add_argument("--recursive", "-r", action="store_true", help="递归子目录")
    parser.add_argument("--max-images", type=int, default=100, help="最多处理多少张")
    parser.add_argument(
        "--formats", "-f",
        default="md,html,docx,pdf,clipboard",
        help="输出格式，逗号分隔。可选：md,html,docx,pdf,clipboard",
    )
    parser.add_argument("--open", action="store_true",
                        help="生成后打开（优先 html → clipboard → docx → pdf）")
    args = parser.parse_args()

    fmts = {f.strip().lower() for f in args.formats.split(",") if f.strip()}
    unknown = fmts - set(ALL_FORMATS)
    if unknown:
        print(f"⚠️ 未知格式: {unknown}，可选: {ALL_FORMATS}")
        return

    print(f"\n🖼️  图片鉴赏: {args.directory}")
    print(f"   输出格式: {', '.join(sorted(fmts))}")

    curator = ImageCurator({
        "generate_html":      "html" in fmts,
        "generate_docx":      "docx" in fmts,
        "generate_pdf":       "pdf" in fmts,
        "generate_clipboard": "clipboard" in fmts,
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
    print(f"   📝 Markdown : {data['article_path']}")
    if data.get("html_path"):
        print(f"   🌐 HTML     : {data['html_path']}")
    if data.get("docx_path"):
        print(f"   📘 Word     : {data['docx_path']}")
    if data.get("pdf_path"):
        print(f"   📄 PDF      : {data['pdf_path']}")
    if data.get("clipboard_path"):
        print(f"   📋 富文本   : {data['clipboard_path']}")
        print(f"      → 浏览器打开后点「复制全文」，粘贴到微信/知乎编辑器")
    print(f"   🖼️  图片     : {data['image_count']} 张")
    print(f"   ⏱️  耗时     : {data['elapsed']}")

    if args.open:
        # 打开优先级：微信富文本 > HTML > Word > PDF
        for key in ("clipboard_path", "html_path", "docx_path", "pdf_path"):
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