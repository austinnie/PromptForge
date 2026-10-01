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
    parser.add_argument("--image", "-i", type=str, default=None,
                        help="参考图路径（图生视频）")    
    parser.add_argument("--open", action="store_true", help="生成后打开视频")
    parser.add_argument("--no-rules", action="store_true", help="关闭提示词规则（一镜到底/禁文字/无台词声音段），做 A/B 对照")
    parser.add_argument("--style-lock", type=str, default=None,
                        help="画风锁定：预设名（watercolor）或一整句英文")
    parser.add_argument("--dialogue", type=str, default=None, help="台词（仅单段视频；一字不改地念出来）")
    parser.add_argument("--speaker", type=str, default=None, help="台词说话人，如：少女")
    parser.add_argument("--voice", type=str, default=None, help="声音设定：年龄/性别/音色/语速/口音")

    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        return

    # --dialogue 目前只支持单段视频（见 skill.py 的 generate()）
    if args.dialogue and args.duration > args.segment_duration:
        print(f"❌ --dialogue 只支持单段视频（duration <= segment-duration）；"
              f"当前 duration={args.duration}, segment-duration={args.segment_duration}")
        print(f"  多镜台词请用分镜方案（见 skills/video_generator/README.md）")
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

    # 加载参考图（图生视频）
    ref_img = None
    if args.image:
        from PIL import Image
        try:
            ref_img = Image.open(args.image).convert("RGB")
            print(f"🖼️  使用参考图: {args.image}")
        except Exception as e:
            print(f"⚠️ 参考图加载失败: {e}")
            
    result = generator.generate(
        prompt=args.prompt,
        duration=args.duration,
        width=args.width,
        height=args.height,
        reference_image=ref_img,
        apply_prompt_rules=not args.no_rules,
        style_lock=args.style_lock,
        dialogue=args.dialogue,
        speaker=args.speaker,
        voice=args.voice,
    )

    if result["status"] == "success":
        data = result["result"]
        print(f"\n✅ 生成完成！")
        print(f"   📁 视频: {data['video_path']}")
        print(f"   ⏱️  时长: {data.get('duration', 'unknown')}s")
        print(f"   📹 片段: {data.get('segments', 1)}")
        print(f"   ⏱️  耗时: {data.get('elapsed', 'unknown')}")
        if data.get("final_prompt"):
            print(f"   📝 最终提示词:\n{data['final_prompt']}")

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