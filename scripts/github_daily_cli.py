#!/usr/bin/env python
"""
🐙 GitHub 仓库日报 CLI

用法:
  # 完全自动（抓 Trending → 挑一个 → 写 → 排版 → 推送）
  python scripts/github_daily_cli.py

  # 指定仓库
  python scripts/github_daily_cli.py --repo langgenius/dify

  # 只排版不推送
  python scripts/github_daily_cli.py --no-publish

  # 生成全部内容但不推送 + 打开预览
  python scripts/github_daily_cli.py --no-publish --open

  # 不生成配图（节省 API 额度）
  python scripts/github_daily_cli.py --no-illustration
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.github_repo_daily import GitHubRepoDaily


def main():
    parser = argparse.ArgumentParser(description="🐙 GitHub 仓库日报")
    parser.add_argument("--repo", help="指定仓库 owner/repo（不填则抓 Trending）")
    parser.add_argument("--no-publish", action="store_true", help="不推送公众号（只排版）")
    parser.add_argument("--no-illustration", action="store_true", help="不生成配图")
    parser.add_argument("--words", type=int, default=1200, help="文章字数")
    parser.add_argument("--theme", default="newspaper", help="微信排版主题")
    parser.add_argument("--open", action="store_true", help="完成后打开预览")
    args = parser.parse_args()

    skill = GitHubRepoDaily({
        "wechat_theme": args.theme,
    })

    print(f"\n🐙 GitHub 仓库日报")
    if args.repo:
        print(f"   指定仓库: {args.repo}")
    else:
        print(f"   自动抓 Trending")

    r = skill.execute(
        force_repo=args.repo,
        force_publish=False if args.no_publish else None,
        skip_illustration=args.no_illustration,
        words=args.words,
    )

    if r["status"] != "success":
        print(f"\n❌ 失败: {r.get('error')}")
        return

    d = r["result"]
    print(f"\n✅ 完成！")
    print(f"   📦 仓库:     {d['repo']}")
    print(f"   ⭐ Stars:    {d['repo_stars']}")
    print(f"   📄 文章:     {d['article_md']}")
    print(f"   📝 标题:     {d['article_title']}")
    print(f"   ✍️  字数:     {d['article_words']}")
    print(f"   🎨 配图:     {len(d.get('images', []))} 张")
    if d.get("cover"):
        print(f"   🖼️  封面:     {d['cover']}")
    if d.get("wechat_preview"):
        print(f"   📱 预览:     {d['wechat_preview']}")
    print(f"   {'✅ 已推送' if d.get('published') else '⏸️ 未推送'}")
    print(f"   ⏱️  耗时:     {d.get('elapsed')}")

    if args.open:
        import os
        # 优先打开微信预览
        for key in ("wechat_preview", "article_md"):
            p = d.get(key)
            if p and Path(p).exists():
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
                break


if __name__ == "__main__":
    main()