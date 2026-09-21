#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PromptForge 每周技术文章任务

流程：
  1) TechHotArticle 生成文章 + 配图（Word/JSON）
  2) 读 JSON → 拼成 Markdown
  3) WechatFormatter 排版（内联样式 HTML）
  4) 生成封面（可选）
  5) 推送到公众号草稿箱（默认推送）

用法：
  python scripts/weekly_tech_task.py
  python scripts/weekly_tech_task.py --style 深度技术型 --theme newspaper
  python scripts/weekly_tech_task.py --no-publish       # 只生成
  python scripts/weekly_tech_task.py --open             # 完成后打开预览
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not (PROJECT_ROOT / "skills" / "tech_hot_article").is_dir():
    sys.exit(f"❌ 项目根目录识别失败：{PROJECT_ROOT}")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_markdown(article_json: dict, out_md: Path) -> str:
    """把 TechHotArticle 的 JSON 拼成带配图的 Markdown"""
    import re
    article = article_json["article"]
    # 防御：万一 title 还带 Markdown 标题前缀，剥干净
    title = re.sub(r"^#+\s*", "", article["title"]).strip() or "未命名"
    body = article["body"]

    image_positions = {
        int(k): v for k, v in (article_json.get("image_positions") or {}).items()
    }

    # 复用内部的分段逻辑
    from skills.tech_hot_article import TechHotArticle
    gen = TechHotArticle()
    paragraphs = gen._split_article_into_blocks(body)

    lines = [
        f"# {title}",
        "",
        f"> 热点：{article.get('hot_title', '')} · "
        f"来源：{article.get('hot_source', '')} · "
        f"风格：{article.get('style', '')}",
        "",
        "---",
        "",
    ]

    for i, para in enumerate(paragraphs):
        lines.append(para)
        lines.append("")
        if i in image_positions:
            img = Path(image_positions[i]).resolve().as_posix()
            lines.append(f"![配图 {i + 1}]({img})")
            lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    return title


def main() -> int:
    parser = argparse.ArgumentParser(description="PromptForge 每周技术文章任务")
    parser.add_argument("--style", "-s", default=None,
                        help="写作风格：专业分析型/通俗科普型/深度技术型/行业观察型/趋势预测型")
    parser.add_argument("--theme", "-t", default="newspaper",
                        help="微信排版主题（默认 newspaper）")
    parser.add_argument("--footer-image", type=Path,
                        default=Path("assets/qr/公众号结束处.png"),
                        help="文末二维码")
    parser.add_argument("--no-publish", action="store_true",
                        help="只生成不推草稿箱（默认推送）")
    parser.add_argument("--no-cover", action="store_true",
                        help="跳过封面生成")
    parser.add_argument("--open", action="store_true",
                        help="完成后打开浏览器预览")
    args = parser.parse_args()

    # 加载 .env
    try:
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    t0 = time.time()

    # ---------- 1. 生成技术文章 ----------
    print("=" * 62)
    print("  1/5  生成技术文章")
    print("=" * 62)
    from skills.tech_hot_article import TechHotArticle
    gen = TechHotArticle()
    result = gen.execute(style=args.style)
    if result["status"] != "success":
        print(f"❌ 生成失败：{result.get('error')}")
        return 1

    data = result["result"]
    article_file = Path(data["article_file"])
    if not article_file.exists():
        print(f"❌ JSON 不存在：{article_file}")
        return 1
    article_json = json.loads(article_file.read_text(encoding="utf-8"))

    # ---------- 2. 拼 Markdown ----------
    print("\n" + "=" * 62)
    print("  2/5  生成 Markdown")
    print("=" * 62)
    out_dir = PROJECT_ROOT / "output" / "weekly_tech"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "article.md"
    title = build_markdown(article_json, md_path)
    print(f"📝 {md_path}")

    # ---------- 3. 微信排版 ----------
    print("\n" + "=" * 62)
    print("  3/5  微信排版")
    print("=" * 62)
    from skills.wechat_formatter import WechatFormatter
    fmt = WechatFormatter()

    footer_image = (PROJECT_ROOT / args.footer_image).resolve()
    fmt_result = fmt.format(
        str(md_path),
        theme=args.theme,
        footer_image=str(footer_image) if footer_image.exists() else None,
        open=False,
    )
    if fmt_result["status"] != "success":
        print(f"❌ 排版失败：{fmt_result.get('error')}")
        return 1

    article_dir = fmt_result["result"]["article_dir"]
    preview_path = fmt_result["result"]["preview_path"]
    print(f"🎨 {article_dir}")
    print(f"🌐 {preview_path}")

    # ---------- 4. 生成封面 ----------
    cover_path = None
    if not args.no_cover:
        print("\n" + "=" * 62)
        print("  4/5  生成封面")
        print("=" * 62)
        cover_res = fmt.generate_cover(title, data.get("hot_topic", ""))
        if cover_res["status"] == "success":
            cover_path = cover_res["result"]["cover_path"]
            print(f"🖼️  {cover_path}")
        else:
            print(f"⚠️  封面生成失败：{cover_res.get('error')}（跳过，微信要求必须有封面）")

    # ---------- 5. 推送 ----------
    print("\n" + "=" * 62)
    print("  5/5  推送公众号草稿箱")
    print("=" * 62)
    published = False
    if args.no_publish:
        print("⏭️  已跳过（--no-publish）")
    else:
        pub_res = fmt.publish(article_dir, cover_path=cover_path)
        if pub_res["status"] == "success":
            print("✅ 已推送到公众号草稿箱")
            published = True
        else:
            print(f"❌ 推送失败：{pub_res.get('error')}")
            print("   排查：1) .env 里 WECHAT_APP_ID/SECRET  2) 出口 IP 是否在白名单  3) 账号是否认证")

    # ---------- 收尾 ----------
    elapsed = time.time() - t0
    print("\n" + "=" * 62)
    print("  🎉 全部完成")
    print("=" * 62)
    print(f"📄 标题      : {title}")
    print(f"📁 Markdown  : {md_path}")
    print(f"🎨 排版目录  : {article_dir}")
    print(f"🌐 预览页面  : {preview_path}")
    print(f"🖼️  封面      : {cover_path or '（未生成）'}")
    print(f"📤 已推送    : {'是' if published else '否'}")
    print(f"⏱️  耗时      : {elapsed:.1f}s")

    if args.open:
        webbrowser.open(Path(preview_path).resolve().as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())