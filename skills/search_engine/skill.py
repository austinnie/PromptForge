"""
search_engine - 匿名搜索引擎

功能:
  - 匿名搜索（DuckDuckGo，无账号、不追踪、不记录）
  - 图片 / 视频 / 网页
  - 一键下载（图片直下，视频走 video_player）

依赖:
  pip install ddgs
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# 优先新包名 ddgs，回退旧包名 duckduckgo_search
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_AVAILABLE = True
    except ImportError:
        DDGS_AVAILABLE = False


class SearchEngine:
    """匿名搜索引擎"""

    name = "search_engine"
    version = "1.0.0"

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    # 已知会 403 的图床，直接跳过，避免用户看到裸错
    _BLOCKED_HOSTS = {
        "699pic.com", "zhimg.com", "sinaimg.cn",
        "weibo.com", "alicdn.com", "360buyimg.com",
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        if not DDGS_AVAILABLE:
            logger.warning("ddgs 未安装，搜索不可用。pip install ddgs")

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": str(PROJECT_ROOT / "output" / "search_engine"),
            "image_dir":  str(PROJECT_ROOT / "output" / "search_engine" / "images"),
            "video_dir":  str(PROJECT_ROOT / "output" / "search_engine" / "videos"),
            "max_results": 20,
            "log_level": "INFO",
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        for key in ("output_dir", "image_dir", "video_dir"):
            Path(self.config[key]).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------
    def search(self, query: str, kind: str = "images",
               limit: int = 20) -> List[Dict[str, Any]]:
        if not DDGS_AVAILABLE:
            return []

        try:
            with DDGS() as ddgs:
                if kind == "images":
                    raw = list(ddgs.images(query, max_results=limit* 2))
                elif kind == "videos":
                    raw = list(ddgs.videos(query, max_results=limit))
                elif kind == "text":
                    raw = list(ddgs.text(query, max_results=limit))
                else:
                    return []
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

        results: List[Dict[str, Any]] = []
        for r in raw:
            if kind == "images":
                img_url = r.get("image", "")
                # 搜索阶段就跳过已知不可下载的来源
                if img_url:
                    host = urlparse(img_url).netloc.lower()
                    if any(b in host for b in self._BLOCKED_HOSTS):
                        continue
                results.append({
                    "kind":      "image",
                    "title":     r.get("title", ""),
                    "url":       img_url,
                    "thumbnail": r.get("thumbnail", ""),
                    "source":    r.get("source", ""),
                    "page":      r.get("url", ""),
                    "width":     r.get("width", 0),
                    "height":    r.get("height", 0),
                })
            elif kind == "videos":
                results.append({
                    "kind":        "video",
                    "title":       r.get("title", ""),
                    "url":         r.get("content") or r.get("url", ""),
                    "thumbnail":   r.get("image", ""),
                    "duration":    r.get("duration", ""),
                    "publisher":   r.get("publisher") or r.get("uploader", ""),
                    "description": r.get("description", ""),
                })
            else:
                results.append({
                    "kind":    "text",
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", ""),
                })

        logger.info(f"搜索 '{query}' ({kind}) → {len(results)} 条")
        return results[:limit]

    # ------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------
    def download_image(self, url: str,
                       save_dir: Optional[str] = None,
                       filename: Optional[str] = None,
                       referer: Optional[str] = None) -> Dict[str, Any]:
        save_dir_path = Path(save_dir or self.config["image_dir"])
        save_dir_path.mkdir(parents=True, exist_ok=True)

        host = urlparse(url).netloc.lower()
        if any(b in host for b in self._BLOCKED_HOSTS):
            return {"status": "error",
                    "error": f"该来源（{host}）禁止下载，请换一张"}
                    
        if not filename:
            ext = Path(urlparse(url).path).suffix.lower()
            if ext not in self.IMAGE_EXTS:
                ext = ".jpg"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"img_{ts}{ext}"
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        target = save_dir_path / filename

        # 从图片 URL 推断 Referer（多数图床校验同域名）
        if not referer:
            p = urlparse(url)
            referer = f"{p.scheme}://{p.netloc}/"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": referer,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            r = requests.get(url, headers=headers, timeout=30, stream=True)
            r.raise_for_status()
            with open(target, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            size = target.stat().st_size
            logger.info(f"下载: {target.name} ({size / 1024:.1f} KB)")
            return {"status": "success", "path": str(target), "size": size}
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return {"status": "error", "error": str(e)}
            
    def download_batch_items(self, items: List[Dict[str, str]]) -> Dict[str, Any]:
        """items: [{"url": ..., "referer": ...}, ...]"""
        ok, fail = [], []
        for it in items:
            r = self.download_image(it["url"], referer=it.get("referer"))
            if r["status"] == "success":
                ok.append(r["path"])
            else:
                fail.append({"url": it["url"], "error": r.get("error")})
        return {"status": "success", "downloaded": ok, "failed": fail}
        
    # ------------------------------------------------------------
    # execute
    # ------------------------------------------------------------
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        action:
          search                query, [kind=images|videos|text], [limit]
          download_image        url, [filename], [referer]
          download_batch_items  items=[{"url": ..., "referer": ...}, ...]
        """
        action = kwargs.get("action", "")
        if not action:
            return {"status": "error", "error": "缺少 action"}

        try:
            if action == "search":
                q = (kwargs.get("query") or "").strip()
                if not q:
                    return {"status": "error", "error": "缺少 query"}
                kind = kwargs.get("kind", "images")
                limit = int(kwargs.get("limit", self.config["max_results"]))
                hits = self.search(q, kind, limit)
                return {"status": "success",
                        "result": {"query": q, "kind": kind,
                                   "results": hits, "count": len(hits)}}

            if action == "download_image":
                u = kwargs.get("url")
                if not u:
                    return {"status": "error", "error": "缺少 url"}
                r = self.download_image(
                    u,
                    kwargs.get("save_dir"),
                    kwargs.get("filename"),
                    referer=kwargs.get("referer"),
                )
                return {"status": r["status"], "result": r,
                        "error": r.get("error")}

            if action == "download_batch_items":
                items = kwargs.get("items") or []
                if not items:
                    return {"status": "error", "error": "缺少 items"}
                r = self.download_batch_items(items)
                return {"status": "success", "result": r}
                


            return {"status": "error", "error": f"未知 action: {action}"}

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<SearchEngine v{self.version} ddgs={DDGS_AVAILABLE}>"