"""
video_sniffer - 网页视频嗅探器

输入网页 URL，自动识别页面里所有可下载的视频。
解析结果交给 video_player 播放 / 下载。

依赖: pip install yt-dlp
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


def _fmt_duration(secs) -> str:
    if not secs:
        return ""
    total = int(secs)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoSniffer:
    """网页视频嗅探器"""

    name = "video_sniffer"
    version = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_config()
        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp 未安装，嗅探功能不可用。pip install yt-dlp")

    def _setup_config(self):
        defaults = {
            "max_entries": 50,      # playlist 最多展开多少条
            "timeout": 30,          # socket 超时
            "flat_mode": True,      # True=快，部分字段空；False=慢，字段全
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    # ------------------------------------------------------------
    # 分析入口
    # ------------------------------------------------------------
    def analyze(self, url: str) -> Dict[str, Any]:
        """分析网页，返回可下载的视频列表"""
        if not YT_DLP_AVAILABLE:
            return {"status": "error", "error": "yt-dlp 未安装"}
        if not url:
            return {"status": "error", "error": "缺少 URL"}

        opts = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "socket_timeout": self.config["timeout"],
            "extract_flat": "in_playlist" if self.config["flat_mode"] else False,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"分析失败: {e}")
            return {"status": "error", "error": str(e)}

        if not info:
            return {"status": "error", "error": "无返回结果"}

        if info.get("_type") == "playlist":
            entries = [e for e in (info.get("entries") or []) if e]
            items = [self._to_item(e) for e in entries[: self.config["max_entries"]]]
            title = info.get("title") or "播放列表"
            kind = "playlist"
            total = len(entries)
        else:
            items = [self._to_item(info)]
            title = info.get("title") or "视频"
            kind = "single"
            total = 1

        # 过滤掉没有可用 URL 的条目
        items = [it for it in items if it.get("url")]

        logger.info(f"嗅探 {url} → {len(items)}/{total} 条 ({kind})")
        return {
            "status": "success",
            "result": {
                "url":    url,
                "kind":   kind,
                "title":  title,
                "count":  len(items),
                "total":  total,
                "items":  items,
            },
        }

    def _to_item(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """把 yt-dlp 的 entry 转成统一格式"""
        vid = entry.get("id", "")
        url = entry.get("webpage_url") or entry.get("url") or ""

        # flat 模式有时只给 ID，需要拼回完整 URL
        extractor = (entry.get("extractor_key") or entry.get("extractor") or "").lower()
        if url and not url.startswith(("http://", "https://")):
            if "youtube" in extractor:
                url = f"https://www.youtube.com/watch?v={url}"
            elif "bilibili" in extractor:
                url = f"https://www.bilibili.com/video/{url}"
            elif "twitter" in extractor or "x.com" in extractor:
                url = ""
            else:
                url = ""

        dur = entry.get("duration") or 0
        return {
            "title":        entry.get("title") or entry.get("fulltitle") or "未知",
            "url":          url,
            "id":           vid,
            "duration":     dur,
            "duration_str": _fmt_duration(dur),
            "uploader":     entry.get("uploader") or entry.get("channel") or "",
            "thumbnail":    entry.get("thumbnail") or "",
            "source":       extractor or "unknown",
            "description":  (entry.get("description") or "")[:200],
        }

    # ------------------------------------------------------------
    # execute
    # ------------------------------------------------------------
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        action:
          analyze  url          解析网页，返回视频列表
          info     url          只拿第一条详情（单视频快速路径）
        """
        action = kwargs.get("action", "analyze")
        url = kwargs.get("url", "")

        try:
            if action == "analyze":
                return self.analyze(url)
            if action == "info":
                r = self.analyze(url)
                if r.get("status") != "success":
                    return r
                items = r["result"].get("items", [])
                if not items:
                    return {"status": "error", "error": "未发现视频"}
                return {"status": "success", "result": items[0]}
            return {"status": "error", "error": f"未知 action: {action}"}
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<VideoSniffer v{self.version} yt_dlp={YT_DLP_AVAILABLE}>"