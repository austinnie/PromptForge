#!/usr/bin/env python
"""
🎨 图像生成 CLI

用法:
  python image_generator_cli.py "a beautiful sunset"           # 文生图
  python image_generator_cli.py "sunset" --width 1024 --height 1024
  python image_generator_cli.py "make it oil painting" --input ref.png   # 图生图
  python image_generator_cli.py --engines                      # 列出可用引擎
"""

import sys
import os
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.image_generator import ImageGenerator


def main():
    parser = argparse.ArgumentParser(
        description="🎨 图像生成 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python image_generator_cli.py "a beautiful sunset over the ocean"
  python image_generator_cli.py "sunset" --engine pollinations
  python image_generator_cli.py "make it oil painting" --input ref.png --strength 0.6
  python image_generator_cli.py --engines
        """
    )

    parser.add_argument("prompt", nargs="?", type=str, help="提示词")
    parser.add_argument("--width", "-W", type=int, default=1024, help="宽度 (默认 1024)")
    parser.add_argument("--height", "-H", type=int, default=1024, help="高度 (默认 1024)")
    parser.add_argument("--steps", "-s", type=int, default=25, help="推理步数 (默认 25)")
    parser.add_argument("--cfg", "-c", type=float, default=7.5, help="引导强度 (默认 7.5)")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--engine", "-e", type=str, default=None, help="引擎名称 (agnes/pollinations/huggingface)")
    parser.add_argument("--input", "-i", type=str, default=None, help="参考图路径（图生图）")
    parser.add_argument("--strength", type=float, default=0.7, help="图生图强度 (默认 0.7)")
    parser.add_argument("--engines", action="store_true", help="列出可用引擎")
    parser.add_argument("--open", action="store_true", help="生成后自动打开图片")

    args = parser.parse_args()

    generator = ImageGenerator({})

    if args.engines:
        print("\n🎨 可用图像引擎:")
        for e in ImageGenerator.AVAILABLE_ENGINES:
            print(f"  - {e}")
        return

    if not args.prompt:
        parser.print_help()
        return

    print(f"\n🎨 图像生成: {args.prompt[:50]}...")
    print(f"   引擎: {args.engine or generator.get_engine()}")
    print(f"   尺寸: {args.width}x{args.height}")

    if args.input:
        # 图生图
        from PIL import Image
        if not os.path.exists(args.input):
            print(f"❌ 参考图不存在: {args.input}")
            return
        init_image = Image.open(args.input)
        result = generator.generate_from_image(
            prompt=args.prompt,
            image=init_image,
            strength=args.strength,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
            seed=args.seed,
            engine=args.engine,
        )
    else:
        # 文生图
        result = generator.generate(
            prompt=args.prompt,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
            seed=args.seed,
            engine=args.engine,
        )

    if result["status"] == "success":
        data = result["result"]
        print(f"\n✅ 生成完成！")
        print(f"   📁 图片: {data['image_path']}")
        print(f"   🎨 引擎: {data['engine']}")
        if "seed" in data:
            print(f"   🎲 种子: {data['seed']}")
        if "elapsed" in data:
            print(f"   ⏱️  耗时: {data['elapsed']}")

        if args.open:
            try:
                if sys.platform == "win32":
                    os.startfile(data["image_path"])
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", data["image_path"]])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", data["image_path"]])
                print("\n📂 正在打开图片...")
            except:
                pass
    else:
        print(f"\n❌ 生成失败: {result.get('error')}")


if __name__ == "__main__":
    main()