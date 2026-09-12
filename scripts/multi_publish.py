"""
一键多平台分发：公众号 + 小红书 + 快手 + 抖音

用法：
    # 公众号 + 小红书 + 快手
    python scripts/multi_publish.py output\机甲2 --platforms wechat,xiaohongshu,kuaishou

    # 所有平台
    python scripts/multi_publish.py output\机甲2 --platforms all

    # 只发公众号
    python scripts/multi_publish.py output\机甲2 --platforms wechat

    # 跳过鉴赏（复用已有文章目录）
    python scripts/multi_publish.py output\articles\20260912_XXX_机甲2 --skip-curate --platforms all
"""

import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.image_curator import ImageCurator
from skills.social_auto_upload import SocialAutoUpload
from skills.social_auto_upload.skill import NOTE_PLATFORMS

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

WECHAT_PLATFORM = "wechat"
ALL_SOCIAL = list(NOTE_PLATFORMS)          # ["douyin", "kuaishou", "xiaohongshu"]
ALL_PLATFORMS = [WECHAT_PLATFORM] + ALL_SOCIAL


# ---------- 公众号 ----------

def publish_to_wechat(article_md: Path, theme: str, dry_run: bool) -> dict:
    """公众号：排版 → 推草稿箱"""
    if not article_md.exists():
        return {"status": "error", "error": f"文章不存在: {article_md}"}

    try:
        from skills.wechat_formatter import WechatFormatter
    except Exception as e:
        return {"status": "error", "error": f"wechat_formatter 加载失败: {e}"}

    fmt = WechatFormatter()

    # 1) 排版
    print(f"  → 排版 ({theme})...")
    result = fmt.format(str(article_md), theme=theme, open=False)
    if result["status"] != "success":
        return {"status": "error", "error": f"排版失败: {result.get('error')}"}

    article_dir = result["result"]["article_dir"]
    print(f"  → 已排版: {article_dir}")

    # 2) 推草稿箱
    print(f"  → 推送草稿箱...")
    pub = fmt.publish(article_dir, dry_run=dry_run)
    if pub["status"] != "success":
        return {"status": "error", "error": f"推送失败: {pub.get('error')}"}

    return {"status": "success", "article_dir": article_dir}


# ---------- 主流程 ----------

def main():
    parser = argparse.ArgumentParser(description="图片鉴赏 + 多平台发布")
    parser.add_argument("directory", help="图片目录，或已有的文章目录")
    parser.add_argument("--platforms", "-p", default="wechat,xiaohongshu",
                        help="平台，逗号分隔；'all' = 所有支持的平台")
    parser.add_argument("--account", "-a", default="test",
                        help="社交平台账号名（对应 cookies/{platform}_{account}.json）")
    parser.add_argument("--title", "-t", default=None)
    parser.add_argument("--note", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--theme", default="terracotta",
                        help="公众号排版主题（默认 terracotta）")
    parser.add_argument("--skip-curate", action="store_true",
                        help="目录已是文章目录，跳过鉴赏")
    parser.add_argument("--wechat-dry-run", action="store_true",
                        help="公众号只上传图片不推草稿")
    parser.add_argument("--max-images", type=int, default=18,
                        help="社交平台最多发几张图（默认 18）")
    args = parser.parse_args()

    src = Path(args.directory).resolve()
    if not src.exists():
        print(f"❌ 目录不存在: {src}")
        return 1

    # ---------- 1. 鉴赏 ----------
    if args.skip_curate:
        article_dir = src
        title = args.title or article_dir.name
        images = sorted([
            str(p) for p in (article_dir / "assets").iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ])[:args.max_images]
    else:
        print(f"\n🎨 鉴赏: {src}")
        curator = ImageCurator()
        r = curator.curate(str(src), title=args.title)
        if r["status"] != "success":
            print(f"❌ 鉴赏失败: {r.get('error')}")
            return 1
        article_dir = Path(r["result"]["article_dir"])
        title = (args.title or r["result"].get("title") or article_dir.name)[:20]
        images = sorted([
            str(p) for p in (article_dir / "assets").iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ])[:args.max_images]
        print(f"✅ 文章: {article_dir}")

    if not images:
        print(f"❌ assets 目录无图片")
        return 1

    article_md = article_dir / "article.md"
    print(f"📰 标题: {title}")
    print(f"📷 图片: {len(images)} 张")
    print(f"📄 文章: {article_md}")

    # ---------- 2. 解析平台 ----------
    if args.platforms.lower() == "all":
        platforms = list(ALL_PLATFORMS)
    else:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    unknown = [p for p in platforms if p not in ALL_PLATFORMS]
    if unknown:
        print(f"⚠️ 未知平台，已跳过: {unknown}")
    platforms = [p for p in platforms if p in ALL_PLATFORMS]

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    # ---------- 3. 逐平台发布 ----------
    results = {}
    pub = SocialAutoUpload() if any(p in ALL_SOCIAL for p in platforms) else None

    for platform in platforms:
        print(f"\n{'='*60}")
        print(f"🚀 {platform}")
        print(f"{'='*60}")

        if platform == WECHAT_PLATFORM:
            r = publish_to_wechat(article_md, args.theme, args.wechat_dry_run)
        elif platform in ALL_SOCIAL:
            r = pub.publish_note(
                platform=platform,
                images=images,
                title=title,
                note=args.note,
                tags=tags,
                account=args.account,
            )
        else:
            r = {"status": "error", "error": f"未处理: {platform}"}

        results[platform] = r
        if r["status"] == "success":
            print(f"✅ {platform}: 成功")
        else:
            print(f"❌ {platform}: {r.get('error')}")

    # ---------- 4. 汇总 ----------
    print(f"\n{'='*60}")
    print("📊 汇总")
    print(f"{'='*60}")
    for platform, r in results.items():
        status = "✅" if r["status"] == "success" else "❌"
        print(f"  {status} {platform}: {r.get('error', '成功')}")

    ok = sum(1 for r in results.values() if r["status"] == "success")
    print(f"\n{len(platforms)} 个平台，成功 {ok} 个")

    if WECHAT_PLATFORM in results and results[WECHAT_PLATFORM]["status"] == "success":
        print(f"\n💡 公众号已推草稿箱，去这里点「群发」:")
        print(f"   https://mp.weixin.qq.com → 内容管理 → 草稿箱")

    return 0 if ok == len(platforms) else 1


if __name__ == "__main__":
    sys.exit(main())