#!/usr/bin/env python
"""
🎬 视频生成 CLI

用法:
  python video_generator_cli.py "月光下的森林"                # 生成 60 秒视频
  python video_generator_cli.py "日落" --duration 30          # 生成 30 秒视频
  python video_generator_cli.py "海边" --duration 120         # 生成 120 秒视频
"""

import sys
import os
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.video_generator import VideoGenerator


def main():
    parser = argparse.ArgumentParser(
        description="🎬 视频生成 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("prompt", nargs="?", type=str, help="提示词")
    parser.add_argument("--duration", "-d", type=int, default=60, help="目标时长（秒，默认 60）")
    parser.add_argument("--segment-duration", "-sd", type=int, default=10, help="单段时长（秒，默认 10）")
    parser.add_argument("--width", "-W", type=int, default=768, help="宽度（默认 768）")
    parser.add_argument("--height", "-H", type=int, default=768, help="高度（默认 768）")
    parser.add_argument("--engine", "-e", type=str, default="agnes", help="引擎名称")
    parser.add_argument("--open", action="store_true", help="生成后打开视频")

    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        return

    print(f"\n🎬 视频生成: {args.prompt[:50]}...")
    print(f"   引擎: {args.engine}")
    print(f"   时长: {args.duration}s ({args.segment_duration}s/段)")

    generator = VideoGenerator({
        "engine": args.engine,
        "segment_duration": args.segment_duration,
        "video_width": args.width,
        "video_height": args.height,
    })

    result = generator.generate(
        prompt=args.prompt,
        duration=args.duration,
        width=args.width,
        height=args.height,
    )

    if result["status"] == "success":
        data = result["result"]
        print(f"\n✅ 生成完成！")
        print(f"   📁 视频: {data['video_path']}")
        print(f"   ⏱️  时长: {data.get('duration', 'unknown')}s")
        print(f"   📹 片段: {data.get('segments', 1)}")
        print(f"   ⏱️  耗时: {data.get('elapsed', 'unknown')}")

        if args.open:
            try:
                if sys.platform == "win32":
                    os.startfile(data["video_path"])
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", data["video_path"]])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", data["video_path"]])
                print("\n📂 正在打开视频...")
            except:
                pass
    else:
        print(f"\n❌ 生成失败: {result.get('error')}")


if __name__ == "__main__":
    main()