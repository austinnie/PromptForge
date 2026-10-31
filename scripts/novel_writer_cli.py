#!/usr/bin/env python
"""
📖 AI 小说生成 CLI

用法:
  # 新建
  python scripts/novel_writer_cli.py --genre 科幻 --title "星际漂流" \
      --outline "人类发现虫洞，探索未知星系" \
      --characters "船长李卓，AI 助手小林" \
      --chapter-count 3 --words-per-chapter 800

  # 续写（从现有文件继续 2 章）
  python scripts/novel_writer_cli.py --continue-from output/novels/xxx.md --chapter-count 2
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.novel_writer import NovelWriter


def main():
    parser = argparse.ArgumentParser(description="📖 AI 小说生成")
    parser.add_argument("--genre", default="科幻", help="题材（默认：科幻）")
    parser.add_argument("--title", help="小说标题（默认自动生成）")
    parser.add_argument("--outline", help="故事大纲（新建时必填）")
    parser.add_argument("--characters", default="主角一人", help="主要人物")
    parser.add_argument("--chapter-count", type=int, default=3, help="本次生成多少章")
    parser.add_argument("--words-per-chapter", type=int, default=800, help="每章目标字数")
    parser.add_argument("--language", default="zh", choices=["zh", "en"], help="语言")
    parser.add_argument("--continue-from", help="续写模式：已有小说文件路径")
    parser.add_argument("--open", action="store_true", help="完成后打开文件")
    args = parser.parse_args()

    writer = NovelWriter()

    print(f"\n📖 开始创作...")
    print(f"   题材: {args.genre}")
    if args.continue_from:
        print(f"   续写: {args.continue_from}")
    else:
        print(f"   标题: {args.title or '(自动)'}")
        print(f"   大纲: {args.outline}")
    print(f"   章节: {args.chapter_count} 章 × {args.words_per_chapter} 字")

    result = writer.execute(
        genre=args.genre,
        title=args.title,
        outline=args.outline,
        characters=args.characters,
        chapter_count=args.chapter_count,
        words_per_chapter=args.words_per_chapter,
        language=args.language,
        continue_from=args.continue_from,
    )

    if result["status"] != "success":
        print(f"\n❌ 生成失败: {result.get('error')}")
        return

    r = result["result"]
    print(f"\n✅ 完成！")
    print(f"   📄 文件:     {r['novel_file']}")
    print(f"   📚 总章节:   {r['chapter_count']} 章")
    print(f"   ✍️  总字数:   {r['total_words']} 字")
    print(f"   ⏱️  耗时:     {r['elapsed']}")
    print(f"\n📝 简介:\n   {r['summary'][:200]}...")

    if args.open:
        import os
        try:
            if sys.platform == "win32":
                os.startfile(r["novel_file"])
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", r["novel_file"]])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", r["novel_file"]])
            print(f"\n📂 已打开: {r['novel_file']}")
        except Exception as e:
            print(f"⚠️ 打开失败: {e}")


if __name__ == "__main__":
    main()