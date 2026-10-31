#!/usr/bin/env python
"""
🔍 匿名搜索引擎 CLI

用法:
  # 图片搜索
  python scripts/search_cli.py 机甲少女
  python scripts/search_cli.py 机甲少女 --kind images --limit 10 --download

  # 视频搜索
  python scripts/search_cli.py "海边日落" --kind videos
  python scripts/search_cli.py "AI 教程" --kind videos --source youtube

  # 只搜索不下载（默认）
  python scripts/search_cli.py 水墨山水
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.search_engine import SearchEngine


def main():
    parser = argparse.ArgumentParser(description="🔍 匿名搜索引擎")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--kind", choices=["images", "videos"], default="images")
    parser.add_argument("--limit", type=int, default=20, help="返回条数")
    parser.add_argument("--source", help="视频源（bilibili / youtube / dailymotion）")
    parser.add_argument("--download", action="store_true", help="下载结果（图片）")
    parser.add_argument("--save-dir", default="output/search", help="下载目录")
    args = parser.parse_args()

    skill = SearchEngine({"output_dir": args.save_dir})

    print(f"\n🔍 搜索: {args.query} ({args.kind})")

    r = skill.execute(
        action="search",
        query=args.query,
        kind=args.kind,
        limit=args.limit,
        source=args.source,
    )

    if r["status"] != "success":
        print(f"❌ 失败: {r.get('error')}")
        return

    items = r["result"]["items"]
    print(f"\n✅ 找到 {len(items)} 条结果:")
    for i, item in enumerate(items, 1):
        if args.kind == "images":
            title = item.get("title", "")[:50]
            size = f"{item.get('width', 0)}x{item.get('height', 0)}"
            print(f"  {i:2d}. [{size}] {title}")
            print(f"      {item['url'][:90]}")
        else:
            dur = item.get("duration", 0)
            dur_str = f"{int(dur // 60)}:{int(dur % 60):02d}" if dur else "?"
            print(f"  {i:2d}. [{dur_str}] {item['title'][:60]}")
            print(f"      {item['url']}")

    # 下载图片
    if args.download and args.kind == "images":
        print(f"\n⬇️  下载到 {args.save_dir}...")
        batch = skill.execute(
            action="download_batch",
            items=[{"url": it["url"], "referer": it.get("referer")} for it in items],
            save_dir=args.save_dir,
        )
        br = batch.get("result", {})
        print(f"   成功 {br.get('success')}/{br.get('total')} 张")
        print(f"   📁 {br.get('save_dir')}")


if __name__ == "__main__":
    main()