#!/usr/bin/env python
"""
🎵 AI 音乐生成 CLI

用法：
  python scripts/music_cli.py --topic "龙之觉醒" --emotion epic --arrangement symphony --duration 30
  python scripts/music_cli.py --topic "江南雨巷" --emotion peaceful --arrangement chinese
  python scripts/music_cli.py --topic "代码人生" --arrangement electronic --duration 20 --open
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.music_generator.skill import (
    MusicMaestro, EMOTION_CONFIG, ARRANGEMENTS,
)


def main():
    parser = argparse.ArgumentParser(description="🎵 AI 音乐生成")
    parser.add_argument("--topic", "-t", required=True, help="音乐主题")
    parser.add_argument(
        "--emotion", "-e", default="epic",
        choices=list(EMOTION_CONFIG.keys()),
        help=f"情绪: {', '.join(EMOTION_CONFIG.keys())}",
    )
    parser.add_argument(
        "--arrangement", "-a", default="symphony",
        choices=list(ARRANGEMENTS.keys()),
        help=f"编曲: {', '.join(ARRANGEMENTS.keys())}",
    )
    parser.add_argument("--duration", "-d", type=int, default=30, help="时长（秒）")
    parser.add_argument("--complexity", type=int, default=1, choices=[1, 2, 3], help="复杂度")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--no-lyrics", action="store_true")
    parser.add_argument("--backend", choices=["symphony", "numpy_wav", "musicgen"],
                        help="强制后端（默认自动选）")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    maestro = MusicMaestro()

    print(f"\n🎵 音乐创作")
    print(f"   主题:   {args.topic}")
    print(f"   情绪:   {args.emotion} ({EMOTION_CONFIG[args.emotion]['name']})")
    print(f"   编曲:   {args.arrangement} ({ARRANGEMENTS[args.arrangement]['name']})")
    print(f"   时长:   {args.duration}s")
    print(f"   后端:   {args.backend or maestro.hardware['recommended']}")

    r = maestro.execute(
        topic=args.topic, emotion=args.emotion,
        arrangement=args.arrangement, duration=args.duration,
        complexity=args.complexity, language=args.language,
        lyrics=not args.no_lyrics, backend=args.backend,
    )

    if r["status"] != "success":
        print(f"\n❌ 失败: {r.get('error')}")
        return

    d = r["result"]
    print(f"\n✅ 完成")
    print(f"   🎵 音频: {d['audio_file']}")
    if d.get("lyrics_file"):
        print(f"   📝 歌词: {d['lyrics_file']}")
    print(f"   🎨 后端: {d['backend']}")
    print(f"   ⏱️  耗时: {d['elapsed']}")

    if d.get("lyrics"):
        print(f"\n📜 歌词预览:\n")
        for line in d["lyrics"].split("\n")[:12]:
            print(f"   {line}")

    if args.open:
        import os
        p = d["audio_file"]
        if Path(p).exists():
            try:
                if sys.platform == "win32":
                    os.startfile(p)
                elif sys.platform == "darwin":
                    import subprocess; subprocess.Popen(["open", p])
                else:
                    import subprocess; subprocess.Popen(["xdg-open", p])
                print(f"\n📂 已打开: {p}")
            except Exception as e:
                print(f"⚠️ 打开失败: {e}")


if __name__ == "__main__":
    main()