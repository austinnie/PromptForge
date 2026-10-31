#!/usr/bin/env python
"""
📅 每日自动化任务 CLI

用法:
  # 完全随机（从主题池抽）
  python scripts/daily_pipeline_cli.py

  # 指定主题
  python scripts/daily_pipeline_cli.py --topic "机甲少女站在废墟中"

  # 指定主题 + 预设 + 图片数
  python scripts/daily_pipeline_cli.py --topic "水墨山水" --preset chinese_ink --count 3

  # 完整流程（含排版 + 推送公众号）
  python scripts/daily_pipeline_cli.py --publish --open
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.daily_pipeline import DailyPipeline


def main():
    parser = argparse.ArgumentParser(description="📅 每日自动化任务")
    parser.add_argument("--topic", help="主题（不填随机）")
    parser.add_argument("--preset", help="预设名（不填按主题自动匹配）")
    parser.add_argument("--count", type=int, default=6, help="生成几张图")
    parser.add_argument("--theme", default="newspaper", help="微信排版主题")
    parser.add_argument("--qr", help="二维码路径（默认 assets/qr/公众号结束处.png）")
    parser.add_argument("--publish", action="store_true", help="推送到公众号草稿箱")
    parser.add_argument("--skip-curator", action="store_true", help="只生成图，不做鉴赏")
    parser.add_argument("--skip-wechat", action="store_true", help="不做微信排版")
    parser.add_argument("--open", action="store_true", help="完成后打开预览")
    args = parser.parse_args()

    pipeline = DailyPipeline()

    print(f"\n📅 每日任务开始")
    print(f"   主题: {args.topic or '(随机)'}")
    print(f"   预设: {args.preset or '(自动)'}")
    print(f"   图片: {args.count} 张")
    print(f"   排版: {args.theme}")
    print(f"   推送: {'是' if args.publish else '否'}")

    r = pipeline.execute(
        topic=args.topic,
        preset=args.preset,
        count=args.count,
        qr_path=args.qr,
        theme=args.theme,
        publish=args.publish,
        skip_curator=args.skip_curator,
        skip_wechat=args.skip_wechat,
    )

    if r["status"] == "error":
        print(f"\n❌ 失败: {r.get('error')}")
        return

    data = r["result"]
    print(f"\n{'✅' if r['status'] == 'success' else '⚠️'} 完成（状态: {r['status']}）")
    print(f"   📌 主题:     {data['topic']}")
    print(f"   🎨 预设:     {data.get('preset') or '(无)'}")
    print(f"   🖼️  图片:     {len(data.get('images', []))} 张")
    if data.get("article_md"):
        print(f"   📄 文章:     {data['article_md']}")
    if data.get("article_html"):
        print(f"   🌐 HTML:     {data['article_html']}")
    if data.get("wechat_preview"):
        print(f"   📱 预览:     {data['wechat_preview']}")
    if data.get("wechat_article_dir"):
        print(f"   📁 排版目录: {data['wechat_article_dir']}")
    if data.get("published"):
        print(f"   ✅ 已推送到公众号草稿箱")
    print(f"   ⏱️  耗时:     {data.get('elapsed')}")

    if args.open:
        import os
        # 打开优先级：微信预览 > 文章 HTML > 图片目录
        for key in ("wechat_preview", "article_html"):
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