#!/usr/bin/env python3
"""微信公众号草稿箱发布工具

将 format.py 排版后的文章推送到微信公众号草稿箱。

用法:
    # 发布排版好的文章目录
    python3 publish.py --dir /path/to/formatted/article/

    # 指定封面图
    python3 publish.py --dir /path/to/formatted/article/ --cover cover.jpg

    # 直接从 Markdown 一步到位（自动排版+发布）
    python3 publish.py --input article.md --theme elegant
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import html as html_module
import tempfile

import requests

# ── 路径 ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent

def _load_config():
    """从 config.settings 读取配置（PromptForge 统一配置源）"""
    try:
        import sys
        project_root = Path(__file__).parents[3]   # publisher → wechat_formatter → skills → PromptForge
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from config.settings import settings
        return {
            "wechat": {
                "app_id": getattr(settings, "wechat_app_id", ""),
                "app_secret": getattr(settings, "wechat_app_secret", ""),
                "author": getattr(settings, "wechat_author", ""),
            },
            "output_dir": getattr(settings, "wechat_output_dir", "./output/wechat"),
        }
    except Exception as e:
        print(f"⚠️ 读取 settings 失败: {e}")
        return {
            "wechat": {"app_id": "", "app_secret": "", "author": ""},
            "output_dir": "./output/wechat",
        }

CONFIG = _load_config()


# ── 微信 API ─────────────────────────────────────────────────────────
def get_access_token():
    """获取微信 API access_token"""
    wechat = CONFIG.get("wechat", {})
    app_id = wechat.get("app_id")
    app_secret = wechat.get("app_secret")

    if not app_id or not app_secret:
        print("错误: 未配置 WECHAT_APP_ID 或 WECHAT_APP_SECRET，请检查 .env 文件")
        sys.exit(1)

    url = (
        "https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    )
    resp = requests.get(url, timeout=15)
    data = resp.json()

    if "access_token" in data:
        print(f"  token 有效期: {data.get('expires_in', '?')} 秒")
        return data["access_token"]
    else:
        errcode = data.get("errcode", "?")
        errmsg = data.get("errmsg", "未知错误")
        print(f"错误: 获取 access_token 失败 (errcode={errcode}: {errmsg})")
        if errcode == 40164:
            print("  → IP 不在白名单中，请到公众号后台添加当前 IP")
        elif errcode in (40001, 40125):
            print("  → AppSecret 无效，请检查 config.json 中的 app_secret")
        sys.exit(1)


def upload_thumb_image(token, image_path):
    """上传封面图到永久素材库，返回 media_id"""
    url = (
        "https://api.weixin.qq.com/cgi-bin/material/add_material"
        f"?access_token={token}&type=image"
    )

    filename = os.path.basename(image_path)
    ext = Path(image_path).suffix.lower()
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        files = {"media": (filename, f, content_type)}
        resp = requests.post(url, files=files, timeout=30)

    data = resp.json()
    if "media_id" in data:
        return data["media_id"]
    else:
        print(f"错误: 上传封面图失败 - {data}")
        return None


def upload_content_image(token, image_path, max_retries=3):
    """上传正文图片（返回 CDN URL），失败自动重试"""
    import time
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"

    filename = os.path.basename(image_path)
    ext = Path(image_path).suffix.lower()
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")

    for attempt in range(1, max_retries + 1):
        try:
            with open(image_path, "rb") as f:
                files = {"media": (filename, f, content_type)}
                resp = requests.post(url, files=files, timeout=30)

            data = resp.json()
            if "url" in data:
                return data["url"]
            else:
                print(f"  ✗ 上传失败 ({attempt}/{max_retries}) - {filename}: {data}")
        except Exception as e:
            print(f"  ✗ 上传异常 ({attempt}/{max_retries}) - {filename}: {e}")

        if attempt < max_retries:
            time.sleep(2 * attempt)  # 递增等待

    print(f"  ✗ 上传彻底失败 - {filename}")
    return None


def download_external_image(url):
    """下载外部图片到临时文件，返回本地路径"""
    try:
        # 还原 HTML 实体（&amp; → &）
        url = html_module.unescape(url)
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0"
        })
        resp.raise_for_status()

        # 从 URL 或 Content-Type 推断扩展名
        content_type = resp.headers.get("Content-Type", "")
        if "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            ext = ".jpg"

        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"  ✗ 下载失败: {url[:60]}... ({e})")
        return None


def replace_all_images(html, article_dir, token):
    """替换 HTML 中的所有图片（本地+外部）为微信 CDN URL"""
    image_dir = article_dir / "images"
    replaced = 0
    failed = 0

    def replace_src(match):
        nonlocal replaced, failed
        src = match.group(1)

        # 已经是微信 CDN 的图片，跳过
        if "mmbiz.qpic.cn" in src:
            return match.group(0)

        # 外部 URL：先下载再上传
        if src.startswith("http://") or src.startswith("https://"):
            local_path = download_external_image(src)
            if local_path:
                cdn_url = upload_content_image(token, local_path)
                os.unlink(local_path)  # 清理临时文件
                if cdn_url:
                    replaced += 1
                    print(f"  ✓ 外部图片: {src[:60]}...")
                    return f'src="{cdn_url}"'
            failed += 1
            return match.group(0)

        # 本地图片
        local_path = article_dir / src
        if not local_path.exists() and image_dir.exists():
            local_path = image_dir / os.path.basename(src)

        if local_path.exists():
            cdn_url = upload_content_image(token, str(local_path))
            if cdn_url:
                replaced += 1
                print(f"  ✓ {os.path.basename(src)}")
                return f'src="{cdn_url}"'
            else:
                failed += 1
                return match.group(0)
        else:
            print(f"  ✗ 未找到: {src}")
            failed += 1
            return match.group(0)

    html = re.sub(r'src="([^"]+)"', replace_src, html)
    return html, replaced, failed


def get_draft_detail(token, media_id):
    """获取草稿详情（含预览链接）"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/get?access_token={token}"
    data = json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8")
    resp = requests.post(url, data=data,
                         headers={"Content-Type": "application/json"}, timeout=15)
    result = resp.json()
    items = result.get("news_item", [])
    if isinstance(items, list) and items:
        return items[0].get("url", "")
    return ""


def push_draft(
    token,
    title,
    content,
    thumb_media_id=None,
    author="",
    article_type="news",
    image_media_ids=None,
):
    """
    推送草稿到微信公众号

    Args:
        token:            access_token
        title:            标题
        content:          news 模式=HTML 正文；newspic 模式=纯文字说明（<=1000字）
        thumb_media_id:   封面图 media_id（仅 news 模式需要）
        author:           作者（仅 news 模式使用）
        article_type:     "news"（普通文章，默认）或 "newspic"（贴图/图片消息）
        image_media_ids:  贴图模式的图片 media_id 列表（永久素材，最多 20 张）

    Returns:
        成功 → media_id 字符串；失败 → None
    """
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"

    # ---------- 贴图模式 ----------
    if article_type == "newspic":
        if not image_media_ids:
            print("错误: newspic 模式必须提供 image_media_ids")
            return None

        if len(image_media_ids) > 20:
            print(f"⚠️  贴图最多 20 张，当前 {len(image_media_ids)} 张，只取前 20 张")
            image_media_ids = image_media_ids[:20]

        article = {
            "article_type": "newspic",
            "title": title[:20],          # 贴图标题上限 20 字
            "content": content[:1000],    # 贴图正文上限 1000 字
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
            "image_info": {
                "image_list": [
                    {"image_media_id": mid} for mid in image_media_ids
                ]
            },
        }

    # ---------- 普通文章模式 ----------
    else:
        if not thumb_media_id:
            print("错误: news 模式必须提供 thumb_media_id（封面图）")
            return None

        article = {
            "title": title,
            "author": author,
            "content": content,
            "content_source_url": "",
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }

    data = {"articles": [article]}

    # 必须用 ensure_ascii=False，否则中文被转义为 \uXXXX 导致微信计算标题长度错误
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    resp = requests.post(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    result = resp.json()

    if "media_id" in result:
        return result["media_id"]

    # ---------- 错误处理 ----------
    errcode = result.get("errcode", "?")
    errmsg = result.get("errmsg", "未知错误")
    print(f"错误: 推送草稿箱失败 (errcode={errcode}: {errmsg})")

    hints = {
        40001: "access_token 无效，请检查 AppSecret 或重新获取",
        40007: "media_id 无效，可能是图片未成功上传为永久素材",
        40056: "media_id 数量超过限制或类型不匹配",
        40164: "IP 不在白名单，请到公众号后台添加当前公网 IP",
        45009: "接口调用超过限额",
        48001: "接口未授权，账号可能未认证或该类型不支持",
        53500: "已开通帐号迁移，不允许调用此接口",
    }
    if errcode in hints:
        print(f"  → {hints[errcode]}")

    return None


# ── 辅助函数 ──────────────────────────────────────────────────────────
def upload_images_as_material(token, image_paths):
    """
    批量上传本地图片为永久素材，返回 media_id 列表

    Args:
        token:       access_token
        image_paths: 本地图片路径列表（str 或 Path）

    Returns:
        list[str]: 成功上传的 media_id 列表（顺序与输入一致，失败的会跳过）
    """
    media_ids = []
    for i, p in enumerate(image_paths, 1):
        p = Path(p)
        if not p.exists():
            print(f"  ✗ [{i}/{len(image_paths)}] 文件不存在: {p}")
            continue
        mid = upload_thumb_image(token, str(p))  # 复用现有函数
        if mid:
            media_ids.append(mid)
            print(f"  ✓ [{i}/{len(image_paths)}] {p.name} → {mid[:20]}...")
        else:
            print(f"  ✗ [{i}/{len(image_paths)}] 上传失败: {p.name}")
    return media_ids

def extract_title_from_html(html):
    """从 HTML 中提取标题（优先 h1，退化到 h2）"""
    for tag in ("h1", "h2"):
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.DOTALL)
        if match:
            return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return None


def find_cover_image(article_dir, cover_arg=None):
    """找到封面图路径"""
    if cover_arg:
        p = Path(cover_arg)
        if p.exists():
            return p
        # 尝试在 article_dir 下找
        p = article_dir / cover_arg
        if p.exists():
            return p
        print(f"警告: 指定的封面图不存在: {cover_arg}")

    # 在 images/ 目录下找封面图
    image_dir = article_dir / "images"
    if image_dir.exists():
        # 优先找 cover- 开头的文件
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.gif"):
            covers = sorted(image_dir.glob(f"cover*{ext[1:]}"))
            if covers:
                return covers[0]
        # 没有 cover- 开头的，取第一张
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.gif"):
            covers = sorted(image_dir.glob(ext))
            if covers:
                return covers[0]

    return None


# ── 主流程 ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="微信公众号草稿箱发布工具")
    
    # newspic 模式两个都不需要，所以 required=False；news 模式在上面手动校验
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--dir", "-d", help="format.py 的输出目录（news 模式使用）")
    parser.add_argument("--yes", action="store_true",help="跳过交互确认（自动发布）")    
    group.add_argument("--input", "-i", help="Markdown 文件路径（news 模式使用）")
    
    parser.add_argument("--cover", "-c", help="封面图片路径")
    parser.add_argument("--title", "-t", help="文章标题（默认从 HTML 提取）")
    parser.add_argument("--theme", default=None,
                        help="排版主题（仅 --input 模式有效，默认读取 gallery 选中的主题）")
    parser.add_argument("--author", "-a",
                        default=CONFIG.get("wechat", {}).get("author", ""),
                        help="作者名")

    parser.add_argument("--type", choices=["news", "newspic"], default="news",
                        help="草稿类型：news=文章（默认），newspic=贴图")
    parser.add_argument("--images", nargs="*", default=None,
                        help="newspic 模式下要发成贴图的本地图片路径列表")
    parser.add_argument("--content", default="",
                        help="newspic 模式下的文字说明（<=1000字）")
                        
    parser.add_argument("--dry-run", action="store_true",
                        help="只做排版和图片上传，不推送草稿箱（用于测试）")

    args = parser.parse_args()

    # ── newspic 模式：提前返回，不读 article.html ────────────────────
    if args.type == "newspic":
        if not args.images:
            print("错误: --type newspic 必须提供 --images")
            sys.exit(1)

        # 标题兜底：--title > 首图 stem
        title = (args.title or Path(args.images[0]).stem).strip() or "每日一图"

        print(f"\n=== 贴图模式 ===")
        print(f"标题  : {title}")
        print(f"图片数: {len(args.images)}")

        print(f"\n获取 access_token...")
        token = get_access_token()
        print("✓ token 获取成功")

        print(f"\n上传图片为永久素材...")
        image_media_ids = upload_images_as_material(token, args.images)
        if not image_media_ids:
            print("错误: 所有图片上传失败")
            sys.exit(1)
        print(f"  上传完成: {len(image_media_ids)}/{len(args.images)}")

        if args.dry_run:
            print(f"\n[dry-run] 跳过推送草稿箱")
            sys.exit(0)

        print(f"\n推送到草稿箱（贴图）...")
        media_id = push_draft(
            token,
            title=title[:20],
            content=args.content or title,
            article_type="newspic",
            image_media_ids=image_media_ids,
        )
        if media_id:
            print(f"✓ 推送成功: {media_id}")
            sys.exit(0)
        print("✗ 推送失败")
        sys.exit(1)

    # ── news 模式：原有流程 ──────────────────────────────────────────
    if not args.dir and not args.input:
        print("错误: news 模式需要提供 --dir 或 --input")
        sys.exit(1)
        
    # ── 1. 确定文章目录 ──────────────────────────────────────────────
    if args.input:
        # 确定主题：优先命令行指定 > gallery 选中 > 默认
        theme = args.theme
        if not theme:
            gallery_theme_file = Path("/tmp/wechat-format/selected-theme.txt")
            if gallery_theme_file.exists():
                saved = gallery_theme_file.read_text(encoding="utf-8").strip()
                if saved:
                    theme = saved
                    print(f"  使用 gallery 选中的主题: {theme}")
        if not theme:
            theme = CONFIG["settings"]["default_theme"]

        # 先调用 format.py 排版
        input_path = Path(args.input).resolve()
        print(f"=== 第一步：排版 ===")
        format_cmd = [
            sys.executable, str(SCRIPT_DIR / "format.py"),
            "--input", str(input_path),
            "--theme", theme,
            "--no-open",
        ]
        result = subprocess.run(format_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"排版失败:\n{result.stderr}")
            sys.exit(1)
        print(result.stdout)

        # 从 format.py 输出中找到目录
        output_base = Path(CONFIG["output_dir"])
        file_stem = re.sub(r"-(公众号|小红书|微博)$", "", input_path.stem)
        article_dir = output_base / file_stem
    else:
        article_dir = Path(args.dir)

    if not article_dir.exists():
        print(f"错误: 目录不存在 - {article_dir}")
        sys.exit(1)

    # ── 2. 读取文章 HTML ─────────────────────────────────────────────
    print(f"\n=== {'第二步' if args.input else '第一步'}：准备发布 ===")
    article_path = article_dir / "article.html"

    if not article_path.exists():
        # 兼容旧版：从 preview.html 提取
        preview_path = article_dir / "preview.html"
        if preview_path.exists():
            print("未找到 article.html，从 preview.html 提取...")
            preview_content = preview_path.read_text(encoding="utf-8")
            match = re.search(
                r'<div id="wechatHtml">(.*?)</div>\s*<script>',
                preview_content, re.DOTALL
            )
            if match:
                html = match.group(1).strip()
            else:
                print("错误: 无法从 preview.html 提取文章内容")
                sys.exit(1)
        else:
            print(f"错误: 未找到 article.html 或 preview.html")
            sys.exit(1)
    else:
        html = article_path.read_text(encoding="utf-8")

    # ── 3. 提取标题 ──────────────────────────────────────────────────
    title = args.title or extract_title_from_html(html) or article_dir.name
    # 剥掉任意层级的 Markdown 标题前缀 + 头尾空白
    title = re.sub(r"^#+\s*", "", title).strip()
    
    author = args.author
    print(f"标题: {title}")
    print(f"作者: {author}")

    # ── 4. 获取 token ────────────────────────────────────────────────
    print(f"\n获取 access_token...")
    token = get_access_token()
    print("✓ token 获取成功")

    # ── 5. 上传正文图片 ──────────────────────────────────────────────
    # 统计图片数量（本地 + 外部）
    image_dir = article_dir / "images"
    local_count = len(list(image_dir.iterdir())) if image_dir.exists() else 0
    external_count = len(re.findall(r'src="(https?://[^"]+)"', html))
    # 排除已是微信 CDN 的
    external_count -= len(re.findall(r'src="https?://mmbiz\.qpic\.cn[^"]*"', html))
    total_images = local_count + external_count

    if total_images > 0:
        print(f"\n上传正文图片 ({local_count} 本地 + {external_count} 外部)...")
        html, replaced, failed = replace_all_images(html, article_dir, token)
        print(f"  上传完成: {replaced} 成功, {failed} 失败")
        if failed > 0 and replaced == 0:
            print("  错误: 所有图片上传失败，中止发布（不推空图草稿）")
            sys.exit(1)
        elif failed > 0:
            print("  警告: 部分图片上传失败，文章中对应位置可能显示空白")
            resp = input("  继续发布？(y/N) ").strip().lower()
            if resp != "y":
                print("  已中止")
                sys.exit(2)
    else:
        print("\n无正文图片需上传")

    # ── 6. 上传封面图 ────────────────────────────────────────────────
    cover_path = find_cover_image(article_dir, args.cover)
    if cover_path:
        print(f"\n上传封面图: {cover_path.name}")
        thumb_media_id = upload_thumb_image(token, str(cover_path))
        if thumb_media_id:
            print(f"  ✓ media_id: {thumb_media_id[:20]}...")
        else:
            print("  ✗ 封面上传失败")
            thumb_media_id = None
    else:
        print("\n未找到封面图")
        thumb_media_id = None

    if not thumb_media_id:
        print("\n错误: 微信要求必须有封面图。")
        print("  请用 --cover 指定封面图路径，或在 images/ 目录放一张图片")
        sys.exit(1)

    # ── 7. 推送草稿箱 ────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n[dry-run] 跳过推送草稿箱")
        print(f"  类型: {args.type}")
        print(f"  标题: {title}")
        if args.type == "news":
            print(f"  封面 media_id: {thumb_media_id}")
            print(f"  HTML 长度: {len(html)} 字符")
        else:
            print(f"  图片数量: {len(args.images or [])}")
        return

    print(f"\n推送到草稿箱（类型={args.type}）...")

    if args.type == "newspic":
        # 贴图模式
        if not args.images:
            print("错误: --type newspic 必须提供 --images")
            sys.exit(1)

        image_media_ids = upload_images_as_material(token, args.images)
        if not image_media_ids:
            print("错误: 所有图片上传失败")
            sys.exit(1)

        media_id = push_draft(
            token,
            title=title[:20],
            content=args.content or title,
            article_type="newspic",
            image_media_ids=image_media_ids,
        )
    else:
        # 普通文章
        media_id = push_draft(token, title, html, thumb_media_id, author)


if __name__ == "__main__":
    main()
