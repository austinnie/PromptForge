# skills/image_curator/writers.py
"""文章输出辅助（Word / PDF / 剪贴板 / Markdown）。

所有 Writer 都是"可选依赖"，缺失时安全降级（不抛异常，返回 None）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 通用工具
# ============================================================

def make_heading(text: str, level: int = 1) -> str:
    """生成 Markdown 标题。"""
    return f"{'#' * max(1, min(6, level))} {text}\n"


# ============================================================
# WordWriter
# ============================================================

class WordWriter:
    """Markdown/HTML → .docx（需要 python-docx）。"""

    def __init__(self):
        try:
            import docx  # noqa: F401
            self._docx = docx
            self._available = True
        except ImportError:
            self._available = False
            logger.info("python-docx 未安装，WordWriter 不可用（pip install python-docx）")

    @property
    def available(self) -> bool:
        return self._available

    def write(self, entries: list[dict], output_path: Path, title: str = "") -> Optional[str]:
        """entries = [{image_path, description, index}, ...]"""
        if not self._available:
            return None
        try:
            doc = self._docx.Document()
            if title:
                doc.add_heading(title, level=0)
            for e in entries:
                doc.add_picture(str(e["image_path"]), width=self._docx.shared.Inches(5.5))
                desc = e.get("description", "")
                if desc:
                    doc.add_paragraph(desc)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path))
            return str(output_path)
        except Exception as e:
            logger.warning(f"WordWriter 失败: {e}")
            return None


# ============================================================
# PDFWriter
# ============================================================

class PDFWriter:
    """Markdown → .pdf（需要 reportlab）。"""

    def __init__(self):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            self._A4 = A4
            self._canvas = canvas
            self._pdfmetrics = pdfmetrics
            self._UnicodeCIDFont = UnicodeCIDFont
            self._available = True
            # 尝试注册中文字体
            try:
                pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                self._font = "STSong-Light"
            except Exception:
                self._font = "Helvetica"
        except ImportError:
            self._available = False
            logger.info("reportlab 未安装，PDFWriter 不可用（pip install reportlab）")

    @property
    def available(self) -> bool:
        return self._available

    def write(self, entries: list[dict], output_path: Path, title: str = "") -> Optional[str]:
        if not self._available:
            return None
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            c = self._canvas.Canvas(str(output_path), pagesize=self._A4)
            width, height = self._A4
            y = height - 60

            if title:
                c.setFont(self._font, 20)
                c.drawString(40, y, title)
                y -= 40

            for e in entries:
                # 图片
                try:
                    img_path = str(e["image_path"])
                    c.drawImage(img_path, 40, y - 240, width=400, height=240, preserveAspectRatio=True)
                    y -= 260
                except Exception:
                    pass

                # 描述
                desc = e.get("description", "")
                if desc:
                    c.setFont(self._font, 10)
                    for line in self._wrap(desc, 80):
                        if y < 60:
                            c.showPage()
                            y = height - 60
                            c.setFont(self._font, 10)
                        c.drawString(40, y, line)
                        y -= 14
                y -= 10
                if y < 100:
                    c.showPage()
                    y = height - 60

            c.save()
            return str(output_path)
        except Exception as e:
            logger.warning(f"PDFWriter 失败: {e}")
            return None

    @staticmethod
    def _wrap(text: str, width: int):
        lines = []
        for i in range(0, len(text), width):
            lines.append(text[i:i + width])
        return lines or [""]


# ============================================================
# ClipboardWriter
# ============================================================

class ClipboardWriter:
    """Markdown → 剪贴板（需要 pyperclip）。"""

    def __init__(self):
        try:
            import pyperclip  # noqa: F401
            self._pyperclip = pyperclip
            self._available = True
        except ImportError:
            self._available = False
            logger.info("pyperclip 未安装，ClipboardWriter 不可用（pip install pyperclip）")

    @property
    def available(self) -> bool:
        return self._available

    def write(self, text: str) -> bool:
        if not self._available:
            return False
        try:
            self._pyperclip.copy(text)
            return True
        except Exception as e:
            logger.warning(f"ClipboardWriter 失败: {e}")
            return False