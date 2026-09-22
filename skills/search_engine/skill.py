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

try:
    import yandexsearcher
    YANDEX_SEARCHER_AVAILABLE = True
except ImportError:
    YANDEX_SEARCHER_AVAILABLE = False
    
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
        # 图片：百度 → Yandex → ddgs(Bing)
        if kind == "images":
            hits = self._search_baidu_images(query, limit)
            if hits:
                return hits
            logger.warning("百度图片无结果，回退 Yandex")

            hits = self._search_yandex_images(query, limit)
            if hits:
                return hits
            logger.warning("Yandex 图片无结果，回退 ddgs（Bing）")


        # 视频：优先走 video_player（B站 + YouTube），失败回退 ddgs
        if kind == "videos":
            hits = self._search_videos_via_vp(query, limit)
            if hits:
                return hits
            logger.warning("video_player 视频无结果，回退 ddgs")
            
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
    # 百度图片搜索（无 Key 直连）
    # ------------------------------------------------------------
    def _search_baidu_images(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """调百度图片 JSON 接口，无需 API Key"""
        import json as _json

        url = "https://image.baidu.com/search/acjson"
        params = {
            "tn":       "resultjson_com",
            "ipn":      "rj",
            "ct":       "201326592",
            "fp":       "result",
            "queryWord": query,
            "cl":       "2",
            "lm":       "-1",
            "ie":       "utf-8",
            "oe":       "utf-8",
            "st":       "-1",
            "word":     query,
            "face":     "0",
            "istype":   "2",
            "nc":       "1",
            "pn":       "0",
            "rn":       str(min(max(limit, 30), 60)),   # 接口最少 30
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://image.baidu.com/",
            "Accept":  "application/json, text/plain, */*",
        }

        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            import json as _json

            text = r.text
            # 百度返回的 JSON 里 URL 带非法反斜杠转义（\p, \x 等），
            # 先把「非合法转义的反斜杠」变成「双反斜杠」
            text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)

            data = _json.loads(text, strict=False)
        except Exception as e:
            logger.error(f"百度图片搜索失败: {e}")
            return []

        results: List[Dict[str, Any]] = []
        for item in (data.get("data") or []):
            if not item:
                continue
            # 原图 URL：replaceUrl[0].ObjURL 是明文的
            img_url = ""
            replace = item.get("replaceUrl") or []
            if replace and isinstance(replace, list):
                img_url = replace[0].get("ObjURL", "") or ""
            if not img_url:
                img_url = item.get("middleURL") or item.get("thumbURL") or ""
            if not img_url:
                continue

            results.append({
                "kind":      "image",
                "title":     item.get("fromPageTitleEnc", "") or "",
                "url":       img_url,
                "thumbnail": item.get("thumbURL", "") or "",
                "source":    item.get("fromURLHost", "") or "",
                "page":      item.get("fromURL", "") or "",
                "width":     item.get("width", 0),
                "height":    item.get("height", 0),
                "engine":    "baidu",
            })
            if len(results) >= limit:
                break

        logger.info(f"百度图片 '{query}' → {len(results)} 条")
        return results
        

    # ------------------------------------------------------------
    # Yandex 图片搜索（yandex-searcher 库）
    # ------------------------------------------------------------
    def _search_yandex_images(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """用 yandex-searcher 搜图片。

        注意：该库底层启动 Selenium/Chrome，单次调用 5~10 秒；
        返回的 URL 是 Yandex 缩略图（-images-thumbs），分辨率较小。
        """
        if not YANDEX_SEARCHER_AVAILABLE:
            return []

        try:
            raw = yandexsearcher.get_picture_urls(query)
        except Exception as e:
            logger.error(f"Yandex 图片搜索失败: {e}")
            return []

        if not raw:
            return []

        results: List[Dict[str, Any]] = []
        for url in raw:
            if not isinstance(url, str):
                continue
            if not url.startswith(("http://", "https://")):
                continue

            # 过滤黑名单
            host = urlparse(url).netloc.lower()
            if any(b in host for b in self._BLOCKED_HOSTS):
                continue

            # 尝试把缩略图 URL 换成更大尺寸（Yandex 内部约定）
            # 原图 URL 通常移除 "-thumbs" 或调大 n 参数

            results.append({
                "kind":      "image",
                "title":     "",
                "url":       url,          # 优先大图
                "thumbnail": url,              # 缩略图留底
                "source":    "",
                "page":      "",
                "width":     0,
                "height":    0,
                "engine":    "yandex",
            })
            if len(results) >= limit:
                break

        logger.info(f"Yandex 图片 '{query}' → {len(results)} 条")
        return results


    def _search_videos_via_vp(self, query, limit=20):
        """复用 video_player 的 B站 + YouTube 搜索"""
        try:
            from skills.video_player import VideoPlayer
            vp = VideoPlayer()
            r = vp.execute(action="search", query=query,
                           source="all", limit=limit)
            if r.get("status") != "success":
                return []
            raw = r["result"].get("results", [])
            # 转换成 search_engine 的标准格式
            results = []
            for v in raw:
                title = (v.get("title") or "").strip()
                # yt-dlp flat 模式下 B站标题可能为空，用 URL 尾段兜底
                if not title or title == "未知":
                    tail = (v.get("url") or "").rstrip("/").split("/")[-1]
                    title = f"B站视频 {tail}" if tail else "未知视频"            
                results.append({
                    "kind":        "video",
                    "title":       title,
                    "url":         v.get("url", ""),
                    "thumbnail":   "",
                    "duration":    v.get("duration_str", ""),
                    "publisher":   v.get("uploader", ""),
                    "description": "",
                    "engine":      v.get("source", "video_player"),
                })
            logger.info(f"video_player 视频 '{query}' → {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"video_player 搜索失败: {e}")
            return []
            
    # ------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------
    def download_image(self, url: str,
                       save_dir: Optional[str] = None,
                       filename: Optional[str] = None,
                       referer: Optional[str] = None) -> Dict[str, Any]:
        import io
        from PIL import Image

        save_dir_path = Path(save_dir or self.config["image_dir"])
        save_dir_path.mkdir(parents=True, exist_ok=True)

        # 域名黑名单：已知拒绝下载的图床
        host = urlparse(url).netloc.lower()
        if any(b in host for b in self._BLOCKED_HOSTS):
            return {"status": "error",
                    "error": f"该来源（{host}）禁止下载，请换一张"}

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

        # 先把整个内容读进内存，才能用 PIL 探格式
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            raw = r.content
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return {"status": "error", "error": str(e)}

        # 用 PIL 读 header 判断真实格式（不解码整图，很快）
        # 用 PIL 读 header 判断真实格式
        real_fmt = ""
        try:
            img = Image.open(io.BytesIO(raw))
            real_fmt = (img.format or "").lower()   # 'jpeg'/'png'/'webp'/'gif'
        except Exception:
            real_fmt = ""

        # webp → png（统一格式，避免 Windows 预览问题）
        if real_fmt == "webp":
            try:
                img = Image.open(io.BytesIO(raw))
                # 有透明通道保留 RGBA，否则 RGB
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                raw = buf.getvalue()
                real_fmt = "png"
                logger.debug("webp 已转 png")
            except Exception as e:
                logger.warning(f"webp 转 png 失败，保留原格式: {e}")

        ext_map = {
            "jpeg": ".jpg", "jpg": ".jpg",
            "png":  ".png",  "gif": ".gif",
            "webp": ".webp", "bmp": ".bmp",
            "tiff": ".tiff", "avif": ".avif",
        }

        # 决定最终扩展名：PIL 探测优先，探测失败退回 URL 后缀
        if real_fmt and real_fmt in ext_map:
            ext = ext_map[real_fmt]
        else:
            ext = Path(urlparse(url).path).suffix.lower()
            if ext not in self.IMAGE_EXTS:
                ext = ".jpg"

        # 生成文件名
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"img_{ts}{ext}"
        else:
            # 用户给定名字：只替换扩展名为真实格式，保留 stem
            base = Path(filename).stem
            filename = f"{base}{ext}"
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        target = save_dir_path / filename

        try:
            target.write_bytes(raw)
            size = target.stat().st_size
            logger.info(
                f"下载: {target.name} ({size / 1024:.1f} KB, {real_fmt or '未知格式'})"
            )
            return {
                "status": "success",
                "path":   str(target),
                "size":   size,
                "format": real_fmt,
            }
        except Exception as e:
            logger.error(f"写入失败: {e}")
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