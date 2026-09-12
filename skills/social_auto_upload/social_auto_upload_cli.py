#!/usr/bin/env python
"""
🌐 多平台内容分发 CLI

用法：
  python social_auto_upload_cli.py login xiaohongshu
  python social_auto_upload_cli.py check xiaohongshu
  python social_auto_upload_cli.py publish-video bilibili video.mp4 "标题" --tid 249
  python social_auto_upload_cli.py publish-note xiaohongshu img1.png img2.png "标题" --tags 机甲,测试
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.social_auto_upload import SocialAutoUpload
from skills.social_auto_upload.skill import (
    SUPPORTED_PLATFORMS, NOTE_PLATFORMS,
)


def cmd_login(args):
    pub = SocialAutoUpload()
    result = pub.login(args.platform, args.account)
    if result["status"] == "success":
        print(f"✅ 登录成功")
        return 0
    print(f"❌ 登录失败: {result.get('error')}")
    return 1


def cmd_check(args):
    pub = SocialAutoUpload()
    result = pub.check(args.platform, args.account)
    print("valid" if result.get("valid") else "invalid")
    return 0 if result.get("valid") else 1


def cmd_publish_video(args):
    pub = SocialAutoUpload()
    tags = args.tags.split(",") if args.tags else None
    result = pub.publish_video(
        platform=args.platform,
        file=args.file,
        title=args.title,
        desc=args.desc,
        tags=tags,
        account=args.account,
        schedule=args.schedule,
        thumbnail=args.thumbnail,
        tid=args.tid,
    )
    if result["status"] == "success":
        print(f"✅ 视频已提交到 {args.platform}")
        return 0
    print(f"❌ 失败: {result.get('error')}")
    return 1


def cmd_publish_note(args):
    pub = SocialAutoUpload()
    tags = args.tags.split(",") if args.tags else None
    result = pub.publish_note(
        platform=args.platform,
        images=args.images,
        title=args.title,
        note=args.note,
        tags=tags,
        account=args.account,
        schedule=args.schedule,
    )
    if result["status"] == "success":
        print(f"✅ 图文已提交到 {args.platform}（{len(args.images)} 张）")
        return 0
    print(f"❌ 失败: {result.get('error')}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="🌐 多平台内容分发")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="登录平台")
    p_login.add_argument("platform", choices=SUPPORTED_PLATFORMS)
    p_login.add_argument("--account", default=None)
    p_login.set_defaults(func=cmd_login)

    p_check = sub.add_parser("check", help="校验账号")
    p_check.add_argument("platform", choices=SUPPORTED_PLATFORMS)
    p_check.add_argument("--account", default=None)
    p_check.set_defaults(func=cmd_check)

    p_video = sub.add_parser("publish-video", help="上传视频")
    p_video.add_argument("platform", choices=SUPPORTED_PLATFORMS)
    p_video.add_argument("file")
    p_video.add_argument("title")
    p_video.add_argument("--desc", default="")
    p_video.add_argument("--tags", default="")
    p_video.add_argument("--account", default=None)
    p_video.add_argument("--schedule", default=None)
    p_video.add_argument("--thumbnail", default=None)
    p_video.add_argument("--tid", type=int, default=None)
    p_video.set_defaults(func=cmd_publish_video)

    p_note = sub.add_parser("publish-note", help="上传图文")
    p_note.add_argument("platform", choices=NOTE_PLATFORMS)
    p_note.add_argument("images", nargs="+")
    p_note.add_argument("title")
    p_note.add_argument("--note", default="")
    p_note.add_argument("--tags", default="")
    p_note.add_argument("--account", default=None)
    p_note.add_argument("--schedule", default=None)
    p_note.set_defaults(func=cmd_publish_note)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()