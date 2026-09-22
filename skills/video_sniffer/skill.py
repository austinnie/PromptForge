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
            "cookies_from_browser": None,   # ← 新增，可填 "chrome"/"edge"/"firefox"
            "cookies_file": None, 
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
        
        # cookie 支持（优先级：cookies_file > cookies_from_browser）
        if self.config.get("cookies_file"):
            opts["cookiefile"] = self.config["cookies_file"]
        elif self.config.get("cookies_from_browser"):
            opts["cookiesfrombrowser"] = (self.config["cookies_from_browser"],)


        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.UnsupportedError as e:
            # yt-dlp 不支持的站点，走 HTML 嗅探兜底
            logger.warning(f"yt-dlp 不支持，尝试 HTML 嗅探: {e}")
            return self._html_fallback(url)
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
    # HTML 嗅探兜底（yt-dlp 不支持的站点）
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # HTML 嗅探兜底（yt-dlp 不支持的站点）
    # ------------------------------------------------------------
    def _html_fallback(self, page_url: str) -> Dict[str, Any]:
        """从页面 HTML 里嗅探 <video> / <source> / m3u8 / mp4 直链"""
        import re
        import requests

        try:
            r = requests.get(
                page_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            r.raise_for_status()
            html = r.text
        except Exception as e:
            return {"status": "error",
                    "error": f"yt-dlp 不支持且 HTML 抓取失败: {e}"}

        urls = set()

        # <video src="...">
        for m in re.finditer(r'<video[^>]+src=["\']([^"\']+)["\']', html):
            urls.add(m.group(1))

        # <source src="...">
        for m in re.finditer(r'<source[^>]+src=["\']([^"\']+)["\']', html):
            urls.add(m.group(1))

        # 裸 m3u8 / mp4
        for pattern in (
            r'https?://[^\s"\'\\<>]+\.m3u8[^\s"\'\\<>]*',
            r'https?://[^\s"\'\\<>]+\.mp4[^\s"\'\\<>]*',
        ):
            for m in re.finditer(pattern, html):
                urls.add(m.group(0))

        # JSON 字段 "url": "..." / "playUrl": "..."
        for m in re.finditer(
            r'"(?:url|src|videoUrl|video_url|playUrl|play_url|source)"\s*:\s*"([^"]+)"',
            html,
        ):
            u = m.group(1).replace("\\/", "/")
            if ".m3u8" in u or ".mp4" in u:
                urls.add(u)

        # 清理
        clean = []
        for u in urls:
            u = u.replace("\\/", "/").strip()
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith(("http://", "https://")):
                continue
            if u in clean:
                continue
            clean.append(u)

        if not clean:
            return {"status": "error",
                    "error": "yt-dlp 不支持该站点，且 HTML 里未发现可下载视频"
                             "（可能是 JS 动态加载）"}

        items = [{
            "title":        f"视频 {i+1}",
            "url":          u,
            "id":           "",
            "duration":     0,
            "duration_str": "",
            "uploader":     "",
            "thumbnail":    "",
            "source":       "html_sniffer",
            "description":  "",
        } for i, u in enumerate(clean)]

        logger.info(f"HTML 嗅探 {page_url} → {len(items)} 条")
        return {
            "status": "success",
            "result": {
                "url":   page_url,
                "kind":  "html",
                "title": page_url.rstrip("/").split("/")[-1] or "网页视频",
                "count": len(items),
                "total": len(items),
                "items": items,
            },
        }
        

    # ------------------------------------------------------------
    # 相关视频提取（从单视频页 HTML 抽推荐列表）
    # ------------------------------------------------------------
    def extract_related(self, page_url: str,
                        max_count: int = 30) -> Dict[str, Any]:
        """从视频页 HTML 里提取"相关视频"链接"""
        import re
        import requests
        from urllib.parse import urlparse, urlunparse

        try:
            r = requests.get(
                page_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            r.raise_for_status()
            html = r.text
        except Exception as e:
            return {"status": "error", "error": f"抓取失败: {e}"}

        base = urlparse(page_url)
        self_path = urlunparse((base.scheme, base.netloc, base.path, "", "", ""))
        found: set = set()

        # 0) 最宽松：直接抽所有 /video/xXXXXX
        for m in re.finditer(r'/video/(x[a-z0-9]{5,})', html):
            vid = m.group(1)
            u = f"{base.scheme}://{base.netloc}/video/{vid}"
            if u == self_path:
                continue
            found.add(u)

        # 1) <a href="...">
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\']', html):
            u = self._normalize_url(m.group(1), base)
            if not u:
                continue
            p = urlparse(u)
            if p.netloc != base.netloc:
                continue
            if not any(k in u for k in ("/video/", "/play/")):
                continue
            u = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
            if u == self_path:
                continue
            found.add(u)

        # 2) 绝对 URL
        for m in re.finditer(
            r'https?://(?:www\.)?' + re.escape(base.netloc) +
            r'/video/(x[a-z0-9]+)',
            html,
        ):
            u = f"{base.scheme}://{base.netloc}/video/{m.group(1)}"
            if u == self_path:
                continue
            found.add(u)

        # 3) JSON 字段
        for m in re.finditer(
            r'"(?:url|videoUrl|video_url|href)"\s*:\s*"([^"]+)"', html,
        ):
            u = self._normalize_url(m.group(1), base)
            if not u:
                continue
            if "/video/" not in u and "/play/" not in u:
                continue
            if urlparse(u).netloc != base.netloc:
                continue
            if u == self_path:
                continue
            found.add(u)

        items = []
        for u in sorted(found)[:max_count]:
            vid = u.rstrip("/").split("/")[-1]
            items.append({
                "title":        f"视频 {vid}",
                "url":          u,
                "id":           vid,
                "duration":     0,
                "duration_str": "",
                "uploader":     "",
                "thumbnail":    "",
                "source":       "related",
                "description":  "",
            })

        logger.info(f"相关视频 {page_url} → {len(items)} 条")
        return {
            "status": "success",
            "result": {
                "url":   page_url,
                "kind":  "related",
                "title": f"相关视频（{len(items)} 条）",
                "count": len(items),
                "total": len(items),
                "items": items,
            },
        }
        
    @staticmethod
    def _normalize_url(u: str, base) -> str:
        """把相对 URL 补全为绝对 URL，失败返回空串"""
        if not u:
            return ""
        u = u.replace("\\/", "/").strip()
        if u.startswith("//"):
            return base.scheme + ":" + u
        if u.startswith("/"):
            return f"{base.scheme}://{base.netloc}{u}"
        if u.startswith(("http://", "https://")):
            return u
        return ""
        
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
            if action == "related":
                return self.extract_related(
                    url, kwargs.get("max_count", 30),
                )
            return {"status": "error", "error": f"未知 action: {action}"}
            
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<VideoSniffer v{self.version} yt_dlp={YT_DLP_AVAILABLE}>"