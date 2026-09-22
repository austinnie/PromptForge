"""
video_player - 视频播放器（公开视频搜索 + 流媒体播放 + 边播边存）

功能:
  - 搜索公开视频（B站 / YouTube）
  - mpv: --ytdl 自动解析 + --stream-record 边播边存
  - VLC 回退: yt-dlp 下载到本地后播放
  - 暂停 / 继续（psutil 进程挂起）
  - 观看历史

说明:
  本工具只搜索和播放公开可访问的内容。
  付费 / 会员 / 版权内容请通过官方渠道观看。
"""

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
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

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def _fmt_duration(secs: Optional[float]) -> str:
    if not secs:
        return ""
    total = int(secs)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _safe_filename(name: str, max_len: int = 80) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:max_len] or "video"


class VideoPlayer:
    """视频播放器"""

    name = "video_player"
    version = "1.0.0"

    SEARCH_PREFIX = {
        "bilibili": "bilisearch",
        "youtube":  "ytsearch",
        "niconico": "nicosearch",
        "soundcloud": "scsearch",
    }

    _MPV_WIN_PATHS = [
        r"C:\Program Files\mpv\mpv.exe",
        r"C:\Program Files (x86)\mpv\mpv.exe",
        r"C:\mpv\mpv.exe",
    ]
    _VLC_WIN_PATHS = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]

    # ------------------------------------------------------------
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

        self.system = platform.system()
        self._proc: Optional[subprocess.Popen] = None
        self._player_kind: Optional[str] = None
        self._current: Optional[Dict[str, Any]] = None
        self._last: Optional[Dict[str, Any]] = None
        self._is_paused = False
        self._volume = int(self.config["default_volume"])
        self._record_path: Optional[Path] = None

        self._mpv = self._find_mpv()
        self._vlc = self._find_vlc()
        self._available_player = (
            "mpv" if self._mpv else ("vlc" if self._vlc else "browser")
        )

        self._history_path = Path(self.config["output_dir"]) / "history.json"
        self._load_history()

        logger.info(
            f"VideoPlayer v{self.version} 就绪 "
            f"(系统={self.system}, 播放器={self._available_player})"
        )
        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp 未安装，搜索与播放不可用")
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，暂停/继续不可用")
        if self._available_player == "browser":
            logger.warning("未找到 mpv / VLC，将用浏览器打开（无暂停/录制）")

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir":   str(PROJECT_ROOT / "output" / "video_player"),
            "download_dir": str(PROJECT_ROOT / "output" / "video_player" / "videos"),
            "default_volume": 80,
            "max_search_results": 15,
            "log_level": "INFO",
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        for key in ("output_dir", "download_dir"):
            Path(self.config[key]).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 播放器探测
    # ------------------------------------------------------------
    def _find_mpv(self) -> Optional[str]:
        p = shutil.which("mpv")
        if p:
            return p
        if self.system == "Windows":
            for path in self._MPV_WIN_PATHS:
                if Path(path).exists():
                    return path
        if self.system == "Darwin":
            m = "/Applications/mpv.app/Contents/MacOS/mpv"
            if Path(m).exists():
                return m
        return None

    def _find_vlc(self) -> Optional[str]:
        for name in ("cvlc", "vlc"):
            p = shutil.which(name)
            if p:
                return p
        if self.system == "Windows":
            for path in self._VLC_WIN_PATHS:
                if Path(path).exists():
                    return path
        if self.system == "Darwin":
            m = "/Applications/VLC.app/Contents/MacOS/VLC"
            if Path(m).exists():
                return m
        return None

    # ------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------
    def search(self, query: str, source: str = "bilibili",
               limit: int = 15) -> List[Dict[str, Any]]:
        if not YT_DLP_AVAILABLE:
            return []

        if source == "all":
            sources = ["bilibili", "youtube", "soundcloud"]
        elif source == "dailymotion":
            sources = ["dailymotion"]            
        elif source in self.SEARCH_PREFIX:
            sources = [source]
        else:
            sources = ["bilibili"]

        results: List[Dict[str, Any]] = []

        # Dailymotion 无官方搜索前缀，单独走 HTML 抓取
        if "dailymotion" in sources:
            results.extend(self._search_dailymotion_html(query, limit))
            sources = [s for s in sources if s != "dailymotion"]
            
        for src in sources:
            try:
                prefix = self.SEARCH_PREFIX[src]
                opts = {
                    "quiet": True,
                    "skip_download": True,
                    "extract_flat": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"{prefix}{limit}:{query}", download=False
                    )
                for e in (info.get("entries") or []):
                    if not e:
                        continue
                    vid = e.get("id", "")
                    url = e.get("url") or e.get("webpage_url") or ""
                    if not url and vid:
                        if src == "bilibili":
                            url = f"https://www.bilibili.com/video/{vid}"
                        else:
                            url = f"https://www.youtube.com/watch?v={vid}"
                    if not url:
                        continue
                    dur = e.get("duration") or 0
                    title = e.get("title") or e.get("alt_title") or ""
                    if not title:
                        tail = url.rstrip("/").split("/")[-1]
                        title = f"{src} {tail}" if tail else "未知"
                  
                    results.append({
                        "title":        title,
                        "url":          url,
                        "uploader":     e.get("uploader") or e.get("channel") or "",
                        "duration":     dur,
                        "duration_str": _fmt_duration(dur),
                        "source":       src,
                    })
            except Exception as e:
                logger.error(f"{src} 搜索失败: {e}")

        return results[:limit]

    def _search_dailymotion_html(self, query: str,
                                 limit: int = 15) -> List[Dict[str, Any]]:
        """抓 Dailymotion 搜索页 HTML，抽视频 id"""
        import requests
        from urllib.parse import quote_plus

        search_url = f"https://www.dailymotion.com/search/{quote_plus(query)}/videos"
        try:
            r = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            r.raise_for_status()
            html = r.text
        except Exception as e:
            logger.error(f"Dailymotion 搜索失败: {e}")
            return []

        seen = set()
        results: List[Dict[str, Any]] = []
        for m in re.finditer(r'/video/(x[a-z0-9]{5,})', html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            results.append({
                "title":        f"dailymotion {vid}",
                "url":          f"https://www.dailymotion.com/video/{vid}",
                "uploader":     "",
                "duration":     0,
                "duration_str": "",
                "source":       "dailymotion",
            })
            if len(results) >= limit:
                break

        logger.info(f"Dailymotion 搜索 '{query}' → {len(results)} 条")
        return results
        
    # ------------------------------------------------------------
    # 播放
    # ------------------------------------------------------------
    def play(self, url: str, record: bool = True) -> Dict[str, Any]:
        if not url:
            return {"status": "error", "error": "缺少 url"}

        self.stop()

        if self._available_player == "mpv":
            return self._play_with_mpv(url, record)
        if self._available_player == "vlc":
            return self._play_with_vlc(url, record)

        webbrowser.open(url)
        return {
            "status": "playing",
            "player": "browser",
            "title": url,
            "record_path": None,
            "message": "已在浏览器打开（无录制/暂停）",
        }

    def _play_with_mpv(self, url: str, record: bool) -> Dict[str, Any]:
        title = "video"
        try:
            with yt_dlp.YoutubeDL({
                "quiet": True, "skip_download": True, "no_warnings": True,
            }) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title") or title
        except Exception as e:
            logger.warning(f"获取标题失败: {e}")

        cmd = [
            self._mpv,
            url,
            "--ytdl=yes",
            "--force-window=yes",
            "--keep-open=yes",
            f"--volume={self._volume}",
            f"--title={title}",
        ]

        rec_path = None
        if record:
            safe = _safe_filename(title)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            rec_path = Path(self.config["download_dir"]) / f"{safe}_{ts}.mkv"
            cmd.append(f"--stream-record={rec_path}")

        if not self._spawn(cmd, "mpv"):
            return {"status": "error", "error": "启动 mpv 失败"}

        self._current = {"title": title, "url": url, "source": "mpv"}
        self._last = dict(self._current)
        self._record_path = rec_path
        self._append_history(self._current)

        return {
            "status": "playing",
            "player": "mpv",
            "title": title,
            "url": url,
            "record_path": str(rec_path) if rec_path else None,
            "message": f"正在播放：{title}",
        }

    def _play_with_vlc(self, url: str, record: bool) -> Dict[str, Any]:
        # record=False：VLC 直接流播（不落盘）
        if not record:
            if not self._spawn(
                [self._vlc, url, "--no-video-title-show"], "vlc"
            ):
                return {"status": "error", "error": "启动 VLC 失败"}
            self._current = {"title": url, "url": url, "source": "vlc"}
            self._last = dict(self._current)
            self._append_history(self._current)
            return {
                "status": "playing",
                "player": "vlc",
                "title": url,
                "url": url,
                "record_path": None,
                "message": "VLC 流播中（未录制）",
            }

        # record=True：yt-dlp 下载 → VLC 播本地
        target_dir = Path(self.config["download_dir"])
        opts = {
            "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
            "merge_output_format": "mp4",
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return {"status": "error", "error": f"下载失败: {e}"}

        title = info.get("title") or "video"
        file_path: Optional[Path] = None
        try:
            file_path = Path(ydl.prepare_filename(info))
        except Exception:
            pass
        if not file_path or not file_path.exists():
            safe = _safe_filename(title)
            candidates = sorted(
                target_dir.glob(f"{safe}*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            file_path = candidates[0] if candidates else None

        if not file_path or not file_path.exists():
            return {"status": "error", "error": "下载完成但找不到文件"}

        if not self._spawn(
            [self._vlc, str(file_path), "--no-video-title-show"], "vlc"
        ):
            return {"status": "error", "error": "启动 VLC 失败"}

        self._current = {
            "title": title, "url": url,
            "file": str(file_path), "source": "vlc",
        }
        self._last = dict(self._current)
        self._append_history(self._current)

        return {
            "status": "playing",
            "player": "vlc",
            "title": title,
            "url": url,
            "record_path": str(file_path),
            "message": f"VLC 播放本地：{title}",
        }

    def _spawn(self, cmd: List[str], kind: str) -> bool:
        try:
            flags = 0
            if self.system == "Windows":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self._player_kind = kind
            self._is_paused = False
            return True
        except Exception as e:
            logger.error(f"启动失败: {e}")
            self._proc = None
            return False

    # ------------------------------------------------------------
    # 控制
    # ------------------------------------------------------------
    def pause(self) -> bool:
        if not self._proc or self._is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，无法暂停")
            return False
        try:
            psutil.Process(self._proc.pid).suspend()
            self._is_paused = True
            logger.info("已暂停")
            return True
        except Exception as e:
            logger.error(f"暂停失败: {e}")
            return False

    def resume(self) -> bool:
        if not self._proc or not self._is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            return False
        try:
            psutil.Process(self._proc.pid).resume()
            self._is_paused = False
            logger.info("已继续")
            return True
        except Exception as e:
            logger.error(f"继续失败: {e}")
            return False

    def stop(self) -> bool:
        # 被挂起的进程必须先恢复，否则 terminate 可能不生效
        if self._is_paused:
            self.resume()

        stopped = False
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                stopped = True
            except Exception as e:
                logger.warning(f"停止失败: {e}")
            finally:
                self._proc = None
                self._player_kind = None
                self._is_paused = False
                self._current = None
        return stopped

    def replay(self) -> Dict[str, Any]:
        """重播上一次播放的视频"""
        if not self._last:
            return {"status": "error", "error": "没有可重播的视频"}
        return self.play(self._last["url"], record=True)
        
    def set_volume(self, v: int) -> bool:
        self._volume = max(0, min(100, int(v)))
        logger.info(f"音量设为 {self._volume}（下次播放生效）")
        return True

    # ------------------------------------------------------------
    # 历史
    # ------------------------------------------------------------
    def _load_history(self):
        self._history: List[Dict[str, Any]] = []
        if not self._history_path.exists():
            return
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._history = data
        except Exception as e:
            logger.warning(f"读取历史失败: {e}")

    def _save_history(self):
        try:
            self._history_path.write_text(
                json.dumps(self._history[-100:], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存历史失败: {e}")

    def _append_history(self, item: Dict[str, Any]):
        self._history.append({
            "title":  item.get("title", ""),
            "url":    item.get("url", ""),
            "source": item.get("source", ""),
            "at":     datetime.now().isoformat(timespec="seconds"),
        })
        self._save_history()

    # ------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        alive = self._proc is not None and self._proc.poll() is None
        return {
            "is_playing":       alive,
            "is_paused":        self._is_paused,
            "current":          self._current,
            "player":           self._player_kind,
            "available_player": self._available_player,
            "volume":           self._volume,
            "record_path":      str(self._record_path) if self._record_path else None,
        }

    # ------------------------------------------------------------
    # execute
    # ------------------------------------------------------------
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        action:
          search  query, [source=bilibili|youtube|all], [limit]
          play    url, [record=True]
          pause / resume / stop
          status
          history
        """
        action = kwargs.get("action", "")
        if not action:
            return {"status": "error", "error": "缺少 action"}

        try:
            if action == "search":
                q = (kwargs.get("query") or "").strip()
                if not q:
                    return {"status": "error", "error": "search 需要 query"}
                hits = self.search(
                    q,
                    kwargs.get("source", "bilibili"),
                    int(kwargs.get("limit", self.config["max_search_results"])),
                )
                return {"status": "success",
                        "result": {"query": q, "results": hits, "count": len(hits)}}

            if action == "play":
                url = kwargs.get("url")
                if not url:
                    return {"status": "error", "error": "play 需要 url"}
                r = self.play(url, record=bool(kwargs.get("record", True)))
                return {
                    "status": "success" if r["status"] == "playing" else "error",
                    "result": r,
                    "error": r.get("error"),
                }

            if action == "pause":
                ok = self.pause()
                return {"status": "success" if ok else "error",
                        "result": {"paused": ok},
                        "error": None if ok else "暂停失败"}

            if action == "resume":
                ok = self.resume()
                return {"status": "success" if ok else "error",
                        "result": {"resumed": ok},
                        "error": None if ok else "继续失败"}

            if action == "stop":
                stopped = self.stop()
                return {"status": "success", "result": {"stopped": stopped}}

            if action == "replay":
                r = self.replay()
                return {
                    "status": "success" if r.get("status") == "playing" else "error",
                    "result": r,
                    "error": r.get("error"),
                }
                
            if action == "status":
                return {"status": "success", "result": self.get_status()}

            if action == "history":
                return {"status": "success",
                        "result": {"history": self._history[-20:],
                                   "count": len(self._history)}}

            return {"status": "error", "error": f"未知操作: {action}"}

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<VideoPlayer v{self.version} player={self._available_player}>"