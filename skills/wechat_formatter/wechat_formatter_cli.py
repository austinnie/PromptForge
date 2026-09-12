#!/usr/bin/env python
"""
🖋️ 微信公众号排版 CLI

用法：
  python wechat_formatter_cli.py article.md                          # 默认主题排版
  python wechat_formatter_cli.py article.md --theme terracotta       # 指定主题
  python wechat_formatter_cli.py article.md --gallery                # 主题画廊
  python wechat_formatter_cli.py article.md --enhance --open         # AI 增强 + 自动打开
  python wechat_formatter_cli.py article.md --theme terracotta --cover --publish  # 一条龙
  python wechat_formatter_cli.py cover --title "标题" --topic "主题"  # 只生成封面
  python wechat_formatter_cli.py publish --dir output/wechat/xxx     # 只推送草稿
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.wechat_formatter import WechatFormatter


def cmd_format(args):
    fmt = WechatFormatter()
    result = fmt.format(
        args.input,
        theme=args.theme,
        gallery=args.gallery,
        enhance=args.enhance,
        open=args.open,
        recommend=args.recommend or [],
    )

    if result["status"] != "success":
        print(f"\n❌ 排版失败: {result.get('error')}")
        return 1

    data = result["result"]
    print(f"\n✅ 完成！")
    print(f"   📰 标题: {data.get('title')}")
    print(f"   📝 字数: {data.get('word_count')}")

    if data.get("gallery_path"):
        print(f"   🌐 画廊: {data['gallery_path']}")
        print(f"   🎨 主题数: {data.get('theme_count')}")
    else:
        print(f"   📄 文章: {data['article_path']}")
        print(f"   🌐 预览: {data['preview_path']}")
        print(f"   🎨 主题: {data.get('theme_name')} ({data.get('theme')})")
    print(f"   ⏱️  耗时: {data['elapsed']}")

    # 可选后续步骤
    if args.cover:
        print(f"\n🎨 生成封面...")
        cover = fmt.generate_cover(data.get("title", ""), data.get("title", ""))
        if cover["status"] == "success":
            print(f"   ✅ {cover['result']['cover_path']}")
            data["cover_path"] = cover["result"]["cover_path"]
        else:
            print(f"   ❌ {cover.get('error')}")

    if args.publish:
        print(f"\n📤 推送草稿箱...")
        pub = fmt.publish(data["article_dir"], data.get("cover_path"), dry_run=args.dry_run)
        if pub["status"] == "success":
            print(f"   ✅ 推送成功")
        else:
            print(f"   ❌ {pub.get('error')}")
            return 1

    print(f"\n📂 输出目录: {data['article_dir']}")
    return 0


def cmd_cover(args):
    fmt = WechatFormatter()
    result = fmt.generate_cover(args.title, args.topic, args.output)

    if result["status"] == "success":
        print(f"\n✅ 封面已生成: {result['result']['cover_path']}")
        return 0
    else:
        print(f"\n❌ 封面生成失败: {result.get('error')}")
        return 1


def cmd_publish(args):
    fmt = WechatFormatter()
    result = fmt.publish(args.dir, args.cover, dry_run=args.dry_run)

    if result["status"] == "success":
        print(f"\n✅ 推送成功")
        return 0
    else:
        print(f"\n❌ 推送失败: {result.get('error')}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="🖋️ 微信公众号排版 / 推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # format（默认）
    p_fmt = sub.add_parser("format", help="排版 Markdown（默认命令）")
    p_fmt.add_argument("input", help="Markdown 文件路径")
    p_fmt.add_argument("--theme", "-t", default=None, help="主题名（默认 newspaper）")
    p_fmt.add_argument("--gallery", "-g", action="store_true", help="打开主题画廊")
    p_fmt.add_argument("--enhance", "-e", action="store_true", help="启用 AI 内容增强")
    p_fmt.add_argument("--open", "-o", action="store_true", help="完成后打开浏览器")
    p_fmt.add_argument("--recommend", nargs="*", default=[], help="画廊推荐主题")
    p_fmt.add_argument("--cover", action="store_true", help="同时生成封面")
    p_fmt.add_argument("--publish", action="store_true", help="排版后推送草稿箱")
    p_fmt.add_argument("--dry-run", action="store_true", help="推送时只上传图片不推草稿")

    # cover
    p_cov = sub.add_parser("cover", help="生成封面图")
    p_cov.add_argument("--title", required=True, help="封面标题")
    p_cov.add_argument("--topic", required=True, help="主题描述")
    p_cov.add_argument("--output", "-o", default=None, help="输出路径")

    # publish
    p_pub = sub.add_parser("publish", help="推送草稿箱")
    p_pub.add_argument("--dir", "-d", required=True, help="排版输出目录")
    p_pub.add_argument("--cover", "-c", default=None, help="封面图路径")
    p_pub.add_argument("--dry-run", action="store_true", help="只上传不推送")

    # 兼容"无子命令"调用：wechat_formatter_cli.py article.md --theme xxx
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("format", "cover", "publish"):
        sys.argv.insert(1, "format")

    args = parser.parse_args()

    if args.command == "format" or args.command is None:
        if not hasattr(args, "input") or not args.input:
            parser.print_help()
            return 1
        return cmd_format(args)
    elif args.command == "cover":
        return cmd_cover(args)
    elif args.command == "publish":
        return cmd_publish(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())