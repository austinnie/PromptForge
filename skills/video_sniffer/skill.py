"""
video_sniffer - 网页视频嗅探器 Skill（P2 补齐版）

功能：
  - yt-dlp 分析：识别 1000+ 站点的视频（B站/YouTube/抖音/快手/微博等）
  - HTML 后备解析：非标准页面抓 <video> / <source> / m3u8 / mp4 直链
  - 相关视频提取：从视频详情页抓相关推荐

依赖：
  - requests（已有）
  - yt-dlp（可选，但强烈推荐）：pip install yt-dlp
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)


def _fmt_duration(secs) -> str:
    """秒数 → "MM:SS" 或 "HH:MM:SS"。"""
    if not secs:
        return "?"
    try:
        secs = int(secs)
    except (ValueError, TypeError):
        return "?"
    if secs < 60:
        return f"0:{secs:02d}"
    if secs < 3600:
        return f"{secs // 60}:{secs % 60:02d}"
    return f"{secs // 3600}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


class VideoSniffer:
    name = "video_sniffer"
    version = "1.0.0"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 浏览器侧可能动态加载，但 yt-dlp 通常能绕过
    YTDLP_SKIP_HOSTS = {
        # 这些站点用 yt-dlp 反而慢/乱，优先 HTML 解析
        "example.com",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/sniffer",
            "timeout": 15,
            "max_direct_links": 20,   # HTML 后备最多返回多少条
        }
        for k, v in self.config.items():
            pass
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """dispatch: action=analyze / related"""
        action = kwargs.get("action", "analyze")
        url = (kwargs.get("url") or "").strip()

        if not url:
            return {"status": "error", "error": "url 不能为空"}

        if action == "analyze":
            return self.analyze(url)
        if action == "related":
            max_count = int(kwargs.get("max_count", 30))
            return self.extract_related(url, max_count)
        return {"status": "error", "error": f"不支持 action: {action}"}

    # ---------- analyze：双引擎 ----------

    def analyze(self, url: str) -> Dict[str, Any]:
        """分析页面，返回可下载的视频列表。

        返回格式：
            {
                "status": "success",
                "result": {
                    "url": "...",
                    "method": "ytdlp" | "html" | "both",
                    "videos": [{title, url, duration, thumbnail, ...}],
                    "elapsed": "..."
                }
            }
        """
        start = time.time()

        videos: List[Dict[str, Any]] = []
        methods_used: List[str] = []

        # ---- 引擎 1：yt-dlp ----
        ytdlp_ok = self._try_ytdlp(url, videos)
        if ytdlp_ok:
            methods_used.append("ytdlp")
            logger.info(f"✅ yt-dlp 找到 {len(videos)} 个视频")

        # ---- 引擎 2：HTML 后备（如果 yt-dlp 没拿到 or 是普通页面）----
        if not videos:
            html_videos = self._html_fallback(url)
            if html_videos:
                videos.extend(html_videos)
                methods_used.append("html")
                logger.info(f"✅ HTML 后备找到 {len(html_videos)} 个直链")

        if not videos:
            return {
                "status": "error",
                "error": "未找到视频（yt-dlp 不支持该站点，HTML 也没抓到 <video>/<source>/mp4）",
                "result": {"url": url, "method": "none", "videos": []},
            }

        return {
            "status": "success",
            "result": {
                "url": url,
                "method": "+".join(methods_used),
                "videos": videos,
                "count": len(videos),
                "elapsed": f"{time.time() - start:.1f}s",
            },
            "metadata": {"skill": self.name, "version": self.version},
        }

    # ---------- yt-dlp 引擎 ----------

    def _try_ytdlp(self, url: str, out_videos: List[Dict[str, Any]]) -> bool:
        """用 yt-dlp 分析（extract_flat 快速模式）。

        成功往 out_videos 里塞，返回 True。
        """
        try:
            import yt_dlp
        except ImportError:
            logger.debug("yt-dlp 未安装，跳过")
            return False

        if any(host in url for host in self.YTDLP_SKIP_HOSTS):
            return False

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,      # 只拿元数据，不解析直链
            "skip_download": True,
            "noplaylist": False,        # 支持播放列表/多个视频
            "timeout": self.config["timeout"],
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.debug(f"yt-dlp 分析失败: {e}")
            return False

        if not info:
            return False

        # 单视频 or 播放列表
        entries = info.get("entries") if "entries" in info else [info]

        for e in entries:
            if not e:
                continue
            item = self._to_item(e)
            if item:
                out_videos.append(item)

        return bool(out_videos)

    def _to_item(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """把 yt-dlp entry 转成统一格式。"""
        url = entry.get("webpage_url") or entry.get("url") or ""
        if not url:
            return None

        return {
            "id": entry.get("id", ""),
            "title": entry.get("title", "").strip() or "(无标题)",
            "url": url,
            "duration": entry.get("duration"),
            "duration_str": _fmt_duration(entry.get("duration")),
            "thumbnail": entry.get("thumbnail", ""),
            "uploader": entry.get("uploader", ""),
            "view_count": entry.get("view_count"),
            "formats_count": len(entry.get("formats") or []),
            "extractor": entry.get("extractor_key", entry.get("extractor", "")),
            "kind": "video",
        }

    # ---------- HTML 后备引擎 ----------

    def _html_fallback(self, page_url: str) -> List[Dict[str, Any]]:
        """从 HTML 里嗅探直链（<video>/<source>/m3u8/mp4）。"""
        try:
            r = requests.get(
                page_url,
                timeout=self.config["timeout"],
                headers=self.DEFAULT_HEADERS,
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning(f"HTML 请求失败: {e}")
            return []

        html = r.text
        base = page_url
        base_host = urlparse(base).netloc

        found: Dict[str, Dict[str, Any]] = {}

        def _add(url: str, title: str = "", kind: str = "direct"):
            if not url:
                return
            full = urljoin(base, url)
            if full in found:
                return
            found[full] = {
                "title": title or f"直链 {len(found) + 1}",
                "url": full,
                "kind": kind,
                "host": urlparse(full).netloc,
                "is_cross_host": urlparse(full).netloc != base_host,
            }

        # 1. <video src="...">
        for m in re.finditer(r'<video[^>]+src="([^"]+)"', html, re.IGNORECASE):
            _add(m.group(1), kind="video_tag")

        # 2. <video ...><source src="...">
        for m in re.finditer(r'<source[^>]+src="([^"]+)"', html, re.IGNORECASE):
            _add(m.group(1), kind="source_tag")

        # 3. .mp4 / .m3u8 / .webm / .flv 直链（HTML 里的字符串）
        for m in re.finditer(
            r'["\']([^"\']+\.(?:mp4|m3u8|webm|flv)(?:\?[^"\']*)?)["\']',
            html,
            re.IGNORECASE,
        ):
            ext = m.group(1).split(".")[-1].split("?")[0].lower()
            _add(m.group(1), kind=f"{ext}_url")

        # 4. data-src（懒加载视频）
        for m in re.finditer(r'data-(?:src|video-src|url)="([^"]+\.(?:mp4|m3u8)[^"]*)"', html):
            _add(m.group(1), kind="data_src")

        # 去重 + 限流
        result = list(found.values())[:self.config["max_direct_links"]]

        # 如果是 m3u8 且带主域名，标注（可能需要 referer 才能下）
        for item in result:
            if ".m3u8" in item["url"]:
                item["hint"] = "m3u8 流，需 ffmpeg 或 yt-dlp 下载"

        return result

    # ---------- 相关视频 ----------

    def extract_related(
        self, page_url: str, max_count: int = 30,
    ) -> Dict[str, Any]:
        """从视频页 HTML 里提取"相关视频"链接。"""
        try:
            r = requests.get(
                page_url,
                timeout=self.config["timeout"],
                headers=self.DEFAULT_HEADERS,
            )
            r.raise_for_status()
        except Exception as e:
            return {"status": "error", "error": f"页面请求失败: {e}"}

        html = r.text
        base_host = urlparse(page_url).netloc
        base = page_url

        # 提取所有 href，过滤同域名 + 看起来像视频详情页的
        links: Dict[str, Dict[str, str]] = {}
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,80})</a>', html):
            href, text = m.group(1), m.group(2).strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full = urljoin(base, href)
            parsed = urlparse(full)
            if parsed.netloc != base_host:
                continue
            if full == base:
                continue

            # 启发式过滤：路径里含 video / watch / v / play / bv 等
            if not re.search(r"/(video|watch|v|play|bv|detail|p)/", parsed.path, re.IGNORECASE):
                continue

            if full not in links:
                links[full] = {"url": full, "title": text or "(无标题)"}

        result = list(links.values())[:max_count]

        return {
            "status": "success",
            "result": {
                "url": page_url,
                "count": len(result),
                "links": result,
            },
        }

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return "VideoSniffer"

    def __repr__(self):
        return "<VideoSniffer>"