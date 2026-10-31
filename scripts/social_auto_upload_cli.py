#!/usr/bin/env python
"""
📤 多平台内容分发 CLI

用法:
  # 查看支持的平台 + sau 状态
  python scripts/social_upload_cli.py --list

  # 登录某平台（扫码）
  python scripts/social_upload_cli.py --login douyin
  python scripts/social_upload_cli.py --login xiaohongshu --account myname

  # 发布视频（dry_run 看命令）
  python scripts/social_upload_cli.py --video video.mp4 --platform douyin \
      --title "标题" --desc "描述" --tags "科技,AI" --dry-run

  # 发布视频（真发）
  python scripts/social_upload_cli.py --video video.mp4 --platform douyin \
      --title "标题" --desc "描述"

  # 发布图文（小红书）
  python scripts/social_upload_cli.py --note img1.jpg img2.jpg img3.jpg \
      --platform xiaohongshu --title "标题" --note-text "正文"

  # 批量分发（同一条内容发多个平台）
  python scripts/social_upload_cli.py --video video.mp4 --title "标题" \
      --platform douyin,kuaishou,xiaohongshu
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.social_auto_upload import (
    SocialAutoUpload, SUPPORTED_PLATFORMS, PLATFORM_NAMES,
)


def _print_result(r, action_name):
    if r["status"] != "success":
        print(f"\n❌ {action_name} 失败: {r.get('error')}")
        if r.get("result", {}).get("stderr"):
            print(f"   stderr: {r['result']['stderr'][:500]}")
        return False

    d = r["result"]
    if d.get("dry_run"):
        print(f"\n🔍 dry_run（{d.get('reason')}）")
        print(f"   命令: {d['cmd_str']}")
        if d.get("hint"):
            print(f"\n💡 {d['hint']}")
    else:
        print(f"\n✅ {action_name} 完成")
        if d.get("stdout"):
            print(f"   stdout:\n{d['stdout'][-500:]}")
        if d.get("hint"):
            print(f"\n💡 {d['hint']}")
    return True


def main():
    parser = argparse.ArgumentParser(description="📤 多平台内容分发")
    # 动作
    parser.add_argument("--list", action="store_true", help="列出平台和支持状态")
    parser.add_argument("--login", metavar="PLATFORM", help="登录平台（扫码）")
    parser.add_argument("--check", metavar="PLATFORM", help="校验登录态")
    parser.add_argument("--video", metavar="FILE", help="发布视频")
    parser.add_argument("--note", nargs="+", metavar="IMG", help="发布图文（多张图片）")
    # 通用
    parser.add_argument("--platform", help="平台（多个用逗号分隔）")
    parser.add_argument("--title", help="标题")
    parser.add_argument("--desc", help="描述（视频）")
    parser.add_argument("--note-text", help="正文（图文）")
    parser.add_argument("--tags", help="标签（逗号分隔）")
    parser.add_argument("--account", help="账号名")
    parser.add_argument("--schedule", help='定时发布 "2026-10-31 20:00"')
    parser.add_argument("--thumbnail", help="封面图")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令")
    args = parser.parse_args()

    skill = SocialAutoUpload({"dry_run": args.dry_run})

    # ---- list ----
    if args.list:
        r = skill.execute(action="list_platforms")
        d = r["result"]
        print(f"\n📋 支持平台: {len(d['all'])}")
        for p in d["all"]:
            note_mark = " 📝" if p in d["note"] else ""
            sch_mark = " ⏰" if p in d["schedule"] else ""
            print(f"   {p:15s} {d['names'].get(p, p)}{note_mark}{sch_mark}")
        print(f"\n   📝 = 支持图文   ⏰ = 支持定时")
        print(f"\n   sau_cli: {'✅ ' + d['sau_path'] if d['sau_available'] else '❌ 未找到'}")
        if not d["sau_available"]:
            print(f"\n   💡 安装方法:")
            print(f"      git clone https://github.com/dreammis/social-auto-upload.git \\")
            print(f"        skills/social_auto_upload/social-auto-upload")
        return

    # ---- login ----
    if args.login:
        r = skill.execute(action="login", platform=args.login, account=args.account)
        _print_result(r, f"登录 {args.login}")
        return

    # ---- check ----
    if args.check:
        r = skill.execute(action="check", platform=args.check, account=args.account)
        _print_result(r, f"检查 {args.check}")
        return

    # ---- publish video ----
    if args.video:
        if not args.platform:
            print("❌ --video 需要 --platform")
            return
        platforms = [p.strip() for p in args.platform.split(",")]
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

        for platform in platforms:
            print(f"\n{'=' * 60}")
            print(f"📤 发布到 {PLATFORM_NAMES.get(platform, platform)}")
            print(f"{'=' * 60}")
            r = skill.execute(
                action="publish_video",
                platform=platform,
                file=args.video,
                title=args.title or Path(args.video).stem,
                desc=args.desc or "",
                tags=tags,
                account=args.account,
                schedule=args.schedule,
                thumbnail=args.thumbnail,
            )
            _print_result(r, f"发布到 {platform}")

            if r["status"] != "success":
                print(f"   跳过后续平台")
                break
        return

    # ---- publish note ----
    if args.note:
        if not args.platform:
            print("❌ --note 需要 --platform")
            return
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

        r = skill.execute(
            action="publish_note",
            platform=args.platform,
            images=args.note,
            title=args.title or "(未命名)",
            note=args.note_text or "",
            tags=tags,
            account=args.account,
            schedule=args.schedule,
        )
        _print_result(r, f"发布图文到 {args.platform}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()