"""
image_curator 多格式输出器

  - WordWriter      → .docx（python-docx）
  - PDFWriter       → .pdf（weasyprint / xhtml2pdf / 浏览器打印版）
  - ClipboardWriter → 内联样式 HTML，一键复制到微信/知乎编辑器
"""

import os
import re
import html
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import base64

logger = logging.getLogger(__name__)


def make_heading(entry: Dict[str, Any]) -> str:
    """从文件名生成友好标题（供 skill.py 与本模块共用）"""
    name = Path(entry["filename"]).stem
    name = re.sub(r"^\d{8}[_\-\s]*", "", name)   # 去日期前缀
    name = re.sub(r"^api[_\-\s]*", "", name)     # 去 api_ 前缀
    name = name.replace("_", " ").strip()
    return (name or f"作品 {entry['index']}")[:40]


# ============================================================
# Word
# ============================================================

class WordWriter:
    """生成 .docx（需 python-docx）"""

    def __init__(self, font_name: str = "Microsoft YaHei",
                 east_asia_font: str = "微软雅黑"):
        self.font_name = font_name
        self.east_asia_font = east_asia_font

    def write(self, path, title: str, intro: str, entries: List[Dict]) -> bool:
        try:
            from docx import Document
            from docx.shared import Pt, Cm, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml.ns import qn
        except ImportError:
            logger.warning("⚠️ 未安装 python-docx，跳过 Word。pip install python-docx")
            return False

        doc = Document()

        # 全局默认字体
        normal = doc.styles["Normal"]
        normal.font.name = self.font_name
        normal.font.size = Pt(11)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), self.east_asia_font)

        # 主标题
        h = doc.add_heading(title, level=0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in h.runs:
            r.font.name = self.font_name
            r._element.rPr.rFonts.set(qn("w:eastAsia"), self.east_asia_font)

        # meta
        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = meta.add_run(f"共 {len(entries)} 张作品 · {datetime.now().strftime('%Y-%m-%d')}")
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

        # 引言
        intro_p = doc.add_paragraph(intro)
        intro_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        doc.add_paragraph()

        for e in entries:
            heading = make_heading(e)
            h2 = doc.add_heading(f"{e['index']}. {heading}", level=2)
            for r in h2.runs:
                r.font.name = self.font_name
                r._element.rPr.rFonts.set(qn("w:eastAsia"), self.east_asia_font)

            img_path = Path(e["source_path"])
            if img_path.exists():
                try:
                    doc.add_picture(str(img_path), width=Cm(14))
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception as ex:
                    logger.warning(f"⚠️ Word 插图失败 {img_path.name}: {ex}")

            p = doc.add_paragraph(e["description"])
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

            fname = doc.add_paragraph()
            r = fname.add_run(e["filename"])
            r.font.size = Pt(8)
            r.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

            doc.add_paragraph()

        doc.save(str(path))
        return True


# ============================================================
# PDF
# ============================================================

_PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Songti SC", "STSong", "SimSun", serif;
       color: #2a2a2a; line-height: 1.75; font-size: 11pt; }
h1 { font-size: 22pt; text-align: center; letter-spacing: 2pt; margin: 0 0 6pt; }
.meta { text-align: center; color: #999; font-size: 9pt; margin: 0 0 24pt; }
.intro { border-top: 1px solid #ddd; border-bottom: 1px solid #ddd;
         padding: 12pt 0; margin: 0 0 28pt; color: #555;
         font-style: italic; text-align: justify; }
.entry { margin-bottom: 32pt; page-break-inside: avoid; }
.entry h2 { font-size: 14pt; margin: 0 0 12pt; padding-left: 8pt;
            border-left: 2pt solid #c25b3b; page-break-after: avoid; }
.entry img { max-width: 100%; max-height: 420pt; display: block;
             margin: 0 auto 12pt; }
.entry .desc { text-align: justify; margin: 0 0 8pt; }
.entry .filename { color: #bbb; font-size: 8pt;
                   font-family: Consolas, monospace; word-break: break-all; }
"""

def _img_to_data_uri(path: Path) -> str:
    """图片转 base64，绕过 xhtml2pdf 对中文路径 / 空格的处理问题"""
    ext = path.suffix.lower().lstrip(".")
    mime_map = {
        "jpg": "jpeg", "jpeg": "jpeg",
        "png": "png", "gif": "gif",
        "webp": "webp", "bmp": "bmp",
    }
    mime = mime_map.get(ext, "png")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{data}"
    
class PDFWriter:
    """生成 .pdf（weasyprint / xhtml2pdf / 浏览器打印版）"""

    def write(self, path, title: str, intro: str, entries: List[Dict],
              article_dir: Path) -> bool:
        html_doc = self._build_html(title, intro, entries)

        # 1) weasyprint
        try:
            from weasyprint import HTML
            HTML(string=html_doc, base_url=str(article_dir)).write_pdf(str(path))
            logger.info("📄 PDF 由 weasyprint 生成")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ weasyprint 生成失败: {e}")

        # 2) xhtml2pdf
        try:
            from xhtml2pdf import pisa
            with open(path, "wb") as f:
                result = pisa.CreatePDF(html_doc, dest=f, encoding="utf-8")
            if not result.err:
                logger.info("📄 PDF 由 xhtml2pdf 生成")
                return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ xhtml2pdf 生成失败: {e}")

        # 3) fallback：生成浏览器打印版
        print_html = Path(path).with_suffix(".print.html")
        print_html.write_text(html_doc, encoding="utf-8")
        logger.warning(f"⚠️ 未安装 PDF 库，已生成浏览器打印版: {print_html}")
        logger.warning("   安装：pip install weasyprint  或  pip install xhtml2pdf")
        logger.warning(f"   或双击 {print_html.name} 后 Ctrl+P → 另存为 PDF")
        return False

    def _build_html(self, title: str, intro: str, entries: List[Dict]) -> str:
        rows = []
        for e in entries:
            heading = html.escape(make_heading(e))
            # 用绝对路径，weasyprint/xhtml2pdf 才能读到本地图片
            # ✅ base64 内嵌，兼容中文路径 / 空格 / 特殊字符
            try:
                img_src = _img_to_data_uri(Path(e["source_path"]))
            except Exception as ex:
                logger.warning(f"⚠️ base64 转换失败 {e['filename']}: {ex}")
                img_src = ""
            desc = html.escape(e["description"])
            fname = html.escape(e["filename"])
            rows.append(
                f'<div class="entry">'
                f'<h2>{e["index"]}. {heading}</h2>'
                f'<img src="{img_src}" alt="{heading}">'
                f'<p class="desc">{desc}</p>'
                f'<p class="filename">{fname}</p>'
                f'</div>'
            )
        return (
            f'<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{html.escape(title)}</title>'
            f'<style>{_PRINT_CSS}</style></head><body>'
            f'<h1>{html.escape(title)}</h1>'
            f'<p class="meta">共 {len(entries)} 张作品 · '
            f'{datetime.now().strftime("%Y-%m-%d")}</p>'
            f'<div class="intro">{html.escape(intro)}</div>'
            + "".join(rows) +
            '</body></html>'
        )


# ============================================================
# 富文本（微信 / 知乎）
# ============================================================

class ClipboardWriter:
    """
    生成内联样式 HTML 页面，用户点"复制全文"后粘贴到微信/知乎编辑器。

    关键：微信编辑器不接受 <style> 标签，所有样式必须 inline。
    """

    def write(self, path, title: str, intro: str, entries: List[Dict]) -> bool:
        content = self._build_inline(title, intro, entries)

        page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>复制到微信/知乎 · {html.escape(title)}</title>
<style>
  body {{ margin:0; font-family:-apple-system,"Microsoft YaHei",sans-serif;
          background:#f5f5f5; color:#2a2a2a; }}
  .toolbar {{ position:sticky; top:0; background:#c25b3b; color:#fff;
              padding:12px 20px; display:flex; align-items:center; gap:16px;
              box-shadow:0 2px 8px rgba(0,0,0,.15); z-index:10; }}
  .toolbar button {{ padding:8px 20px; border:0; border-radius:4px; cursor:pointer;
                     background:#fff; color:#c25b3b; font-weight:bold; font-size:14px; }}
  .toolbar button:hover {{ background:#ffe8e0; }}
  .toolbar .hint {{ font-size:13px; opacity:.92; }}
  .container {{ max-width:680px; margin:20px auto 60px; background:#fff;
                padding:36px 30px; border-radius:6px;
                box-shadow:0 2px 16px rgba(0,0,0,.06); }}
</style>
</head>
<body>
<div class="toolbar">
  <button onclick="copyAll()">📋 复制全文</button>
  <span class="hint">粘贴到微信/知乎编辑器（图片需手动上传）</span>
</div>
<div class="container" id="content">
{content}
</div>
<script>
async function copyAll() {{
  const el = document.getElementById('content');
  const htmlStr = el.innerHTML;
  const textStr = el.innerText;
  try {{
    const item = new ClipboardItem({{
      'text/html':  new Blob([htmlStr], {{type:'text/html'}}),
      'text/plain': new Blob([textStr], {{type:'text/plain'}})
    }});
    await navigator.clipboard.write([item]);
    alert('✅ 已复制！请到微信/知乎编辑器粘贴。');
  }} catch(e) {{
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges(); sel.addRange(range);
    document.execCommand('copy');
    alert('✅ 已复制（兼容模式）。');
  }}
}}
</script>
</body>
</html>"""
        Path(path).write_text(page, encoding="utf-8")
        return True

    def _build_inline(self, title: str, intro: str, entries: List[Dict]) -> str:
        parts = []
        parts.append(
            f'<h1 style="text-align:center;font-size:24px;color:#2a2a2a;'
            f'letter-spacing:2px;margin:0 0 12px;font-weight:700;">'
            f'{html.escape(title)}</h1>'
        )
        parts.append(
            f'<p style="text-align:center;color:#999;font-size:13px;margin:0 0 24px;">'
            f'共 {len(entries)} 张作品 · {datetime.now().strftime("%Y-%m-%d")}</p>'
        )
        parts.append(
            f'<section style="border-top:1px solid #eee;border-bottom:1px solid #eee;'
            f'padding:20px 8px;margin:24px 0;color:#555;font-style:italic;'
            f'font-size:15px;line-height:1.85;text-align:justify;">'
            f'{html.escape(intro)}</section>'
        )

        for e in entries:
            heading = html.escape(make_heading(e))
            asset = e.get("asset_path") or ""
            # 富文本用相对路径，用户本地打开能看到；粘贴到微信时图片需手动传
            parts.append(
                f'<h2 style="font-size:18px;color:#2a2a2a;margin:40px 0 16px;'
                f'padding-left:12px;border-left:3px solid #c25b3b;">'
                f'{e["index"]}. {heading}</h2>'
            )
            if asset:
                parts.append(
                    f'<p style="text-align:center;margin:0 0 20px;">'
                    f'<img src="{html.escape(asset)}" '
                    f'style="max-width:100%;border-radius:4px;display:block;margin:0 auto;">'
                    f'</p>'
                )
            parts.append(
                f'<p style="font-size:15px;line-height:1.9;color:#333;'
                f'text-align:justify;margin:0 0 12px;">'
                f'{html.escape(e["description"])}</p>'
            )
            parts.append(
                f'<p style="font-size:12px;color:#bbb;font-family:monospace;'
                f'word-break:break-all;margin:0 0 32px;">'
                f'{html.escape(e["filename"])}</p>'
            )

        return "\n".join(parts)