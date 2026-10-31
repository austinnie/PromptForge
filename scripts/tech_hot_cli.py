#!/usr/bin/env python
"""
📰 技术热点文章生成 CLI

用法:
  # 自动选热点，随机风格
  python scripts/tech_hot_cli.py

  # 指定主题
  python scripts/tech_hot_cli.py --topic "AI 编程助手的最新进展"

  # 指定风格和字数
  python scripts/tech_hot_cli.py --topic "量子计算" --style 专业分析型 --words 2000

  # 不配图
  python scripts/tech_hot_cli.py --topic "Web3" --images 0

  # 打开生成结果
  python scripts/tech_hot_cli.py --open
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.tech_hot_article import TechHotArticle


def main():
    parser = argparse.ArgumentParser(description="📰 技术热点文章生成")
    parser.add_argument("--topic", help="主题（不填自动选热点）")
    parser.add_argument("--style", help="写作风格（不填随机）")
    parser.add_argument("--words", type=int, default=1500, help="目标字数")
    parser.add_argument("--images", type=int, default=4, help="配图数量（0=不配图）")
    parser.add_argument("--source", help="指定抓取源（hacker_news/devto/techcrunch/github）")
    parser.add_argument("--open", action="store_true", help="完成后打开")
    args = parser.parse_args()

    print(f"\n📰 技术热点文章生成")
    print(f"   主题: {args.topic or '(自动)'}")
    print(f"   风格: {args.style or '(随机)'}")
    print(f"   字数: ~{args.words}")
    print(f"   配图: {args.images} 张")

    skill = TechHotArticle()

    r = skill.execute(
        topic=args.topic,
        style=args.style,
        words=args.words,
        images=args.images,
        source=args.source,
    )

    if r["status"] != "success":
        print(f"\n❌ 失败: {r.get('error')}")
        return

    data = r["result"]
    print(f"\n✅ 完成！")
    print(f"   📄 Markdown: {data['article_md']}")
    if data.get("article_docx"):
        print(f"   📘 Word:     {data['article_docx']}")
    print(f"   ✍️  字数:    {data['word_count']} 字")
    print(f"   🖼️  配图:    {data['images_count']} 张")
    print(f"   ⏱️  耗时:    {data['elapsed']}")
    print(f"   📁 输出目录: {data['output_dir']}")

    if args.open:
        import os
        p = data.get("article_md")
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


if __name__ == "__main__":
    main()