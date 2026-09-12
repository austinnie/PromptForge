"""
只重跑 metadata.json 里描述为空 / 过短的图片，补全后重新生成文章。
用法：
    python skills/image_curator/retry_empty.py output/articles/20260912_085346_机甲
"""
import sys
import json
import time
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PIL import Image
from skills.image_curator import ImageCurator
from skills.image_curator.writers import WordWriter, PDFWriter, ClipboardWriter

MIN_LEN = 50


def main(article_dir):
    article_dir = Path(article_dir).resolve()
    meta_file = article_dir / "metadata.json"
    if not meta_file.exists():
        print(f"❌ 找不到 {meta_file}")
        return

    data = json.loads(meta_file.read_text(encoding="utf-8"))
    entries = data["entries"]
    title, intro = data["title"], data["intro"]

    curator = ImageCurator()
    if not curator._vision_engine:
        print("❌ 视觉引擎不可用")
        return

    targets = [
        e for e in entries
        if not e.get("description") or len(e["description"].strip()) < MIN_LEN
    ]
    print(f"📋 共 {len(entries)} 张，需补跑 {len(targets)} 张")

    fallback_prompt = (
        "请用流畅的中文详细描述这张图片，150 字左右，"
        "涵盖主体、构图、色彩、风格、氛围。只输出正文。"
    )

    for e in targets:
        img_path = Path(e["source_path"])
        if not img_path.exists():
            print(f"⚠️ 文件不存在，跳过: {img_path}")
            continue

        print(f"🔄 [{e['index']:2d}] {img_path.name}")
        for attempt in range(3):
            try:
                with Image.open(img_path) as img:
                    img.load()
                    img = curator._resize_for_vision(img, curator.config["vision_max_size"])
                    prompt = curator.config["description_prompt"] if attempt == 0 else fallback_prompt
                    desc = curator._vision_engine.image_to_text(img, prompt=prompt)
                    desc = (desc or "").strip()
                if len(desc) >= MIN_LEN:
                    e["description"] = desc
                    e["error"] = None
                    print(f"   ✅ {len(desc)} 字")
                    break
                raise Exception(f"返回过短（{len(desc)} 字）")
            except Exception as ex:
                print(f"   ⚠️ 第 {attempt+1} 次失败: {ex}")
                time.sleep(5 * (attempt + 1))
        else:
            print(f"   ❌ 3 次都失败，保留原值")

        time.sleep(max(curator.config["throttle_seconds"], 3))

    # 写回 metadata
    meta_file.write_text(
        json.dumps({"title": title, "intro": intro, "entries": entries},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("💾 metadata.json 已更新")

    # 重新生成各格式
    curator._write_markdown(article_dir / "article.md", title, intro, entries)
    curator._write_html(article_dir / "article.html", title, intro, entries)
    print("📝📄 Markdown + HTML 已更新")

    if WordWriter().write(article_dir / "article.docx", title, intro, entries):
        print("📘 Word 已更新")
    if PDFWriter().write(article_dir / "article.pdf", title, intro, entries, article_dir):
        print("📄 PDF 已更新")
    ClipboardWriter().write(article_dir / "clipboard.html", title, intro, entries)
    print("📋 富文本已更新")
    print("\n✅ 全部完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python retry_empty.py <article_dir>")
        sys.exit(1)
    main(sys.argv[1])