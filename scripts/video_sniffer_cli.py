#!/usr/bin/env python
"""
🎯 网页视频嗅探器 CLI

用法：
  # 嗅探单页
  python scripts/video_sniffer_cli.py "https://www.bilibili.com/video/BVxxxx"

  # 嗅探 + 只看直链
  python scripts/video_sniffer_cli.py "<url>" --kind html

  # 提取相关视频
  python scripts/video_sniffer_cli.py "<url>" --related

  # 嗅探后下载第一个视频（用 yt-dlp）
  python scripts/video_sniffer_cli.py "<url>" --download
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.video_sniffer import VideoSniffer


def main():
    parser = argparse.ArgumentParser(description="🎯 网页视频嗅探器")
    parser.add_argument("url", help="网页 URL")
    parser.add_argument("--related", action="store_true", help="提取相关视频（而非视频列表）")
    parser.add_argument("--kind", choices=["all", "ytdlp", "html"], default="all",
                        help="只显示某种引擎的结果")
    parser.add_argument("--download", action="store_true", help="下载第一个视频（需 yt-dlp）")
    parser.add_argument("--save-dir", default="output/sniffer", help="下载目录")
    args = parser.parse_args()

    skill = VideoSniffer({"output_dir": args.save_dir})

    if args.related:
        print(f"\n🎯 提取相关视频: {args.url}")
        r = skill.execute(action="related", url=args.url, max_count=30)
        if r["status"] != "success":
            print(f"❌ 失败: {r.get('error')}")
            return

        data = r["result"]
        print(f"\n✅ 找到 {data['count']} 个相关链接:")
        for i, link in enumerate(data["links"], 1):
            print(f"  {i:2d}. {link['title'][:50]}")
            print(f"      {link['url']}")
        return

    # ---- 分析视频 ----
    print(f"\n🎯 嗅探: {args.url}")
    r = skill.execute(action="analyze", url=args.url)

    if r["status"] != "success":
        print(f"❌ 失败: {r.get('error')}")
        return

    data = r["result"]
    videos = data["videos"]

    if args.kind != "all":
        videos = [v for v in videos if v.get("kind") == args.kind or
                  (args.kind == "ytdlp" and v.get("kind") == "video")]

    print(f"\n✅ 方法: {data['method']} | 找到 {len(videos)} 个视频 (耗时 {data['elapsed']}):")
    for i, v in enumerate(videos, 1):
        dur = v.get("duration_str") or _fmt(v.get("duration"))
        title = v.get("title", "(无标题)")
        print(f"  {i:2d}. [{dur}] {title[:60]}")
        if v.get("uploader"):
            print(f"      👤 {v['uploader']}")
        print(f"      🔗 {v['url']}")
        if v.get("hint"):
            print(f"      💡 {v['hint']}")

    # ---- 下载 ----
    if args.download and videos:
        first = videos[0]
        print(f"\n⬇️  下载: {first['title'][:50]}")
        try:
            import yt_dlp
            opts = {
                "outtmpl": str(Path(args.save_dir) / "%(title)s.%(ext)s"),
                "quiet": False,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([first["url"]])
            print(f"✅ 下载完成 → {args.save_dir}")
        except ImportError:
            print("❌ yt-dlp 未安装: pip install yt-dlp")
        except Exception as e:
            print(f"❌ 下载失败: {e}")


def _fmt(secs) -> str:
    if not secs:
        return "?"
    try:
        secs = int(secs)
    except (ValueError, TypeError):
        return "?"
    if secs < 60:
        return f"0:{secs:02d}"
    return f"{secs // 60}:{secs % 60:02d}"


if __name__ == "__main__":
    main()