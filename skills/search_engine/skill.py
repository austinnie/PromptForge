"""
search_engine - 匿名搜索引擎 Skill（P2 补齐版）

功能：
  - 图片搜索（百度图片，无需 API key）
  - 视频搜索（yt-dlp：B站 / YouTube / Dailymotion）
  - 图片下载（带防盗链处理）
  - 视频下载（yt-dlp，可选）

依赖：
  - requests
  - 视频搜索可选：yt-dlp
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger(__name__)


class SearchEngine:
    name = "search_engine"
    version = "1.0.0"

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    # 防盗链严重的域名，返回的图基本没法用，直接过滤
    _BLOCKED_HOSTS = {
        "699pic.com", "zhimg.com", "sinaimg.cn", "weibo.com",
        "alicdn.com", "360buyimg.com", "taobao.com", "tmall.com",
        "qunar.com", "meituan.com", "dianping.com",
    }

    # 百度图片 AC 接口
    BAIDU_IMAGE_API = "https://image.baidu.com/search/acjson"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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
            "output_dir": "./output/search",
            "download_timeout": 30,
            "max_image_size_mb": 10,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """dispatch: action=search / download / download_batch"""
        action = kwargs.get("action", "search")

        if action == "search":
            kind = kwargs.get("kind", "images")
            query = (kwargs.get("query") or "").strip()
            limit = int(kwargs.get("limit", 20))
            source = kwargs.get("source")  # images 时忽略

            if not query:
                return {"status": "error", "error": "query 不能为空"}

            if kind == "images":
                items = self._search_images(query, limit)
            elif kind == "videos":
                items = self._search_videos(query, limit, source=source)
            elif kind == "text":
                return {"status": "error", "error": "暂不支持 text 搜索（用 /api/chat_llm）"}
            else:
                return {"status": "error", "error": f"不支持的 kind: {kind}"}

            return {
                "status": "success",
                "result": {
                    "query": query,
                    "kind": kind,
                    "count": len(items),
                    "items": items,
                },
            }

        if action == "download":
            return self._download_one(kwargs)

        if action == "download_batch":
            return self._download_batch(kwargs)

        return {"status": "error", "error": f"不支持 action: {action}"}

    # ---------- 图片搜索 ----------

    def _search_images(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """百度图片搜索（AC 接口）。"""
        results: List[Dict[str, Any]] = []

        # 分页：每页 30
        page_size = 30
        pages = (limit + page_size - 1) // page_size

        for page in range(pages):
            try:
                items = self._fetch_baidu_page(query, page * page_size, page_size)
                results.extend(items)
                if len(results) >= limit:
                    break
                time.sleep(0.3)   # 礼貌延迟
            except Exception as e:
                logger.warning(f"百度图片第 {page + 1} 页失败: {e}")
                break

        return results[:limit]

    def _fetch_baidu_page(
        self, query: str, pn: int, rn: int
    ) -> List[Dict[str, Any]]:
        params = {
            "tn": "resultjson_com",
            "logid": "1234567890",
            "ipn": "rj",
            "ct": "201326592",
            "is": "",
            "fp": "result",
            "fr": "",
            "word": query,
            "queryWord": query,
            "cl": "2",
            "lm": "-1",
            "ie": "utf-8",
            "oe": "utf-8",
            "adpicid": "",
            "st": "-1",
            "z": "",
            "ic": "",
            "hd": "",
            "latest": "",
            "copyright": "",
            "s": "",
            "se": "",
            "tab": "",
            "width": "",
            "height": "",
            "face": "0",
            "istype": "2",
            "qc": "",
            "nc": "1",
            "expermode": "",
            "nojc": "",
            "isAsync": "",
            "pn": pn,
            "rn": rn,
            "gsm": "1e",
            "time": str(int(time.time() * 1000)),
        }

        headers = dict(self.DEFAULT_HEADERS)
        headers["Referer"] = f"https://image.baidu.com/search/index?tn=baiduimage&word={quote(query)}"

        r = requests.get(
            self.BAIDU_IMAGE_API,
            params=params,
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()

        # 百度返回的 JSON 有时带非法转义字符，容错解析
        text = r.text
        try:
            import json
            data = json.loads(text)
        except json.JSONDecodeError:
            # 去除尾随逗号修复
            text = re.sub(r",\s*}", "}", text)
            text = re.sub(r",\s*]", "]", text)
            import json
            data = json.loads(text)

        results: List[Dict[str, Any]] = []
        for item in data.get("data", []):
            if not isinstance(item, dict):
                continue

            thumb = item.get("thumbURL") or item.get("middleURL") or ""
            big = (
                item.get("hoverURL")
                or item.get("replaceUrl", [{}])[0].get("ObjURL", "")
                or item.get("objURL", "")
            )

            if not big and not thumb:
                continue

            url = big or thumb
            # 过滤防盗链域名
            host = urlparse(url).netloc.lower()
            if any(b in host for b in self._BLOCKED_HOSTS):
                continue

            results.append({
                "url": url,
                "thumb": thumb,
                "width": item.get("width", 0),
                "height": item.get("height", 0),
                "title": item.get("fromPageTitleEnc", "")[:100],
                "source": "baidu",
                "referer": headers["Referer"],
            })

        return results

    # ---------- 视频搜索 ----------

    def _search_videos(
        self,
        query: str,
        limit: int = 20,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """用 yt-dlp 搜索公开视频（B站 / YouTube / Dailymotion）。"""
        try:
            import yt_dlp
        except ImportError:
            logger.warning("yt-dlp 未安装，视频搜索不可用（pip install yt-dlp）")
            return []

        # 搜索前缀
        prefix_map = {
            "bilibili": "bilisearch",
            "youtube": "ytsearch",
            "dailymotion": "dmsearch",
        }
        # 默认按 source 选，None 则 B站优先
        src = source or "bilibili"
        prefix = prefix_map.get(src, "ytsearch")

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,   # 只拿元数据，不解析直链（快 10 倍）
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"{prefix}{limit}:{query}", download=False)
        except Exception as e:
            logger.warning(f"yt-dlp 搜索失败: {e}")
            return []

        entries = info.get("entries") if info else []
        if not entries:
            return []

        results: List[Dict[str, Any]] = []
        for e in entries:
            if not e:
                continue
            results.append({
                "id": e.get("id", ""),
                "title": e.get("title", ""),
                "url": e.get("webpage_url") or e.get("url", ""),
                "duration": e.get("duration", 0),
                "uploader": e.get("uploader", ""),
                "thumbnail": e.get("thumbnail", ""),
                "source": src,
                "kind": "video",
            })

        return results[:limit]

    # ---------- 下载 ----------

    def _download_one(self, kwargs) -> Dict[str, Any]:
        url = (kwargs.get("url") or "").strip()
        if not url:
            return {"status": "error", "error": "url 不能为空"}

        filename = kwargs.get("filename")
        referer = kwargs.get("referer")
        save_dir = Path(kwargs.get("save_dir") or self.config["output_dir"])

        try:
            path = self._do_download(url, save_dir, filename, referer)
            return {
                "status": "success",
                "result": {
                    "path": str(path),
                    "url": url,
                    "bytes": path.stat().st_size,
                },
            }
        except Exception as e:
            logger.exception("下载失败")
            return {"status": "error", "error": str(e)}

    def _download_batch(self, kwargs) -> Dict[str, Any]:
        items = kwargs.get("items") or []
        if not items:
            return {"status": "error", "error": "items 不能为空"}

        save_dir = Path(kwargs.get("save_dir") or self.config["output_dir"])
        save_dir.mkdir(parents=True, exist_ok=True)

        results: List[Dict[str, Any]] = []
        success = 0
        for i, item in enumerate(items, 1):
            url = item.get("url")
            if not url:
                continue
            try:
                path = self._do_download(
                    url, save_dir, item.get("filename"), item.get("referer")
                )
                results.append({"url": url, "path": str(path), "ok": True})
                success += 1
                logger.info(f"  [{i}/{len(items)}] ✅ {path.name}")
            except Exception as e:
                results.append({"url": url, "error": str(e), "ok": False})
                logger.warning(f"  [{i}/{len(items)}] ⚠️ 失败: {e}")

        return {
            "status": "success",
            "result": {
                "total": len(items),
                "success": success,
                "failed": len(items) - success,
                "save_dir": str(save_dir),
                "items": results,
            },
        }

    def _do_download(
        self,
        url: str,
        save_dir: Path,
        filename: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> Path:
        """单文件下载（带防盗链 / 超时 / 大小限制）。"""
        save_dir.mkdir(parents=True, exist_ok=True)

        # 自动推断文件名
        if not filename:
            path_part = urlparse(url).path
            fname = Path(path_part).name or f"download_{int(time.time())}"
            if not Path(fname).suffix:
                fname += ".jpg"
            filename = fname

        # 防文件名冲突
        filepath = save_dir / filename
        if filepath.exists():
            stem = filepath.stem
            suffix = filepath.suffix
            filepath = save_dir / f"{stem}_{int(time.time())}{suffix}"

        # 构造 headers
        headers = dict(self.DEFAULT_HEADERS)
        if referer:
            headers["Referer"] = referer
        else:
            host = urlparse(url).netloc
            headers["Referer"] = f"https://{host}/"

        # 下载
        timeout = self.config["download_timeout"]
        max_size = self.config["max_image_size_mb"] * 1024 * 1024

        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        r.raise_for_status()

        # 检查大小
        content_length = int(r.headers.get("Content-Length", 0))
        if content_length > max_size:
            raise RuntimeError(f"文件过大: {content_length / 1024 / 1024:.1f}MB")

        # 流式写入
        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > max_size:
                    f.close()
                    filepath.unlink(missing_ok=True)
                    raise RuntimeError(f"文件过大: >{max_size / 1024 / 1024:.1f}MB")

        return filepath

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return "SearchEngine"

    def __repr__(self):
        return "<SearchEngine>"