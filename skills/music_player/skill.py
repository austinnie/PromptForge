"""
music_player - 音乐播放器（v2）

功能:
  - 本地音乐扫描（带缓存）
  - 在线搜索（yt-dlp）
  - 播放（VLC / mpv / system / browser，进程可控）
  - 下载（yt-dlp → mp3）
  - 情绪播放列表
"""

from __future__ import annotations

import json
import logging
import os
import platform
import random
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

# ---- 可选依赖探测 ----
try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

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

class MusicPlayer:
    """音乐播放器 - 搜索 / 下载 / 播放"""

    name = "music_player"
    version = "2.0.0"

    SUPPORTED_FORMATS = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg")

    MOOD_STYLES = {
        "happy":     ["pop", "dance", "upbeat", "party"],
        "sad":       ["ballad", "acoustic", "slow", "emotional"],
        "relax":     ["chill", "lofi", "ambient", "jazz"],
        "energetic": ["rock", "electronic", "workout", "drum and bass"],
        "focus":     ["classical", "piano", "instrumental", "study"],
        "romantic":  ["love", "r&b", "soul", "romantic"],
        "nostalgic": ["retro", "80s", "90s", "classic"],
    }

    # Windows 常见安装路径
    _VLC_WIN_PATHS = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]

    # ============================================================
    # 初始化
    # ============================================================
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

        # 运行时状态
        self._proc: Optional[subprocess.Popen] = None
        self._player_kind: Optional[str] = None
        
        self._current_track: Optional[Dict[str, Any]] = None
        self._last_track: Optional[Dict[str, Any]] = None    # ← 新增：用于 replay
        
        self._playlist: List[Dict[str, Any]] = []
        self._playlist_index: int = -1
        self._volume: int = int(self.config["default_volume"])   # 0-100
        self._scan_cache: Optional[List[Dict[str, Any]]] = None

        self.system = platform.system()
        self._available_player = self._detect_player()

        self.is_paused = False
        logger.info(
            f"MusicPlayer v{self.version} 就绪 "
            f"(系统={self.system}, 播放器={self._available_player})"
        )

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir":   str(PROJECT_ROOT / "output" / "music_player"),
            "download_dir": str(PROJECT_ROOT / "output" / "music_player" / "downloads"),
            "playlist_dir": str(PROJECT_ROOT / "output" / "music_player" / "playlists"),
            "default_volume": 70,
            "max_search_results": 15,
            "log_level": "INFO",
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

        for key in ("output_dir", "download_dir", "playlist_dir"):
            Path(self.config[key]).mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 播放器探测
    # ============================================================
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
            mac = "/Applications/VLC.app/Contents/MacOS/VLC"
            if Path(mac).exists():
                return mac
        return None

    def _detect_player(self) -> str:
        """mpv > vlc > system（system 走默认程序，无进程控制）"""
        if shutil.which("mpv"):
            return "mpv"
        if self._find_vlc():
            return "vlc"
        return "system"

    # ============================================================
    # 本地扫描（带缓存）
    # ============================================================
    def scan_local(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """扫描本地音乐。默认命中缓存。"""
        if self._scan_cache is not None and not refresh:
            return self._scan_cache

        root = Path(self.config["output_dir"])
        if not root.exists():
            self._scan_cache = []
            return self._scan_cache

        tracks: List[Dict[str, Any]] = []
        for ext in self.SUPPORTED_FORMATS:
            for p in root.rglob(f"*{ext}"):
                info = self._read_tags(p)
                if info:
                    tracks.append(info)

        self._scan_cache = tracks
        logger.info(f"扫描完成：{len(tracks)} 首")
        return tracks

    def _read_tags(self, path: Path) -> Optional[Dict[str, Any]]:
        track: Dict[str, Any] = {
            "path": str(path),
            "title": path.stem,
            "artist": "未知艺术家",
            "album": "未知专辑",
            "duration": 0,
            "format": path.suffix.lower(),
            "size": path.stat().st_size,
        }

        if not MUTAGEN_AVAILABLE:
            return track

        try:
            if path.suffix.lower() == ".mp3":
                audio = MP3(path)
                if audio.get("TPE1"): track["artist"] = str(audio["TPE1"][0])
                if audio.get("TIT2"): track["title"]  = str(audio["TIT2"][0])
                if audio.get("TALB"): track["album"]  = str(audio["TALB"][0])
                track["duration"] = audio.info.length
            elif path.suffix.lower() == ".flac":
                audio = FLAC(path)
                if audio.get("artist"): track["artist"] = audio["artist"][0]
                if audio.get("title"):  track["title"]  = audio["title"][0]
                if audio.get("album"):  track["album"]  = audio["album"][0]
                track["duration"] = audio.info.length
        except Exception as e:
            logger.debug(f"读标签失败 {path.name}: {e}")

        return track

    # ============================================================
    # 搜索
    # ============================================================
    def search_local(self, query: str) -> List[Dict[str, Any]]:
        """在本地扫描结果里模糊匹配"""
        q = query.lower()
        hits = []
        for t in self.scan_local():
            if (q in t["title"].lower()
                    or q in t["artist"].lower()
                    or q in t["album"].lower()):
                hits.append(t)
        logger.debug(f"本地搜索 '{query}' → {len(hits)} 条")
        return hits

    def search_online(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """yt-dlp 搜 YouTube（flat，快）"""
        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp 未安装，跳过在线搜索")
            return []

        try:
            opts = {
                "quiet": True,
                "skip_download": True,
                "extract_flat": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

            results = []
            for entry in (info.get("entries") or []):
                if not entry:
                    continue
                vid = entry.get("id")
                url = entry.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
                if not url:
                    continue
                results.append({
                    "title": entry.get("title", "未知"),
                    "artist": entry.get("uploader") or entry.get("channel") or "未知",
                    "url": url,
                    "duration": entry.get("duration") or 0,
                    "source": "youtube",
                })
            logger.info(f"在线搜索 '{query}' → {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"在线搜索失败: {e}")
            return []

    # ============================================================
    # 播放
    # ============================================================
    def _resolve_stream_url(self, url: str) -> str:
        """用 yt-dlp 把 YouTube 网页 URL 解析成直链，供 VLC 播放。
        失败则返回原 URL。"""
        if not YT_DLP_AVAILABLE:
            return url
        if "youtube.com" not in url and "youtu.be" not in url:
            return url

        try:
            opts = {"quiet": True, "skip_download": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # 优先纯音频格式
                for fmt in reversed(info.get("formats", [])):
                    if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") == "none":
                        return fmt["url"]
                return info.get("url", url)
        except Exception as e:
            logger.warning(f"解析直链失败，使用原 URL: {e}")
            return url

    def play(self, track: Dict[str, Any]) -> Dict[str, Any]:
        """播放一首歌。track 需要 url 或 path。"""
        src = track.get("url") or track.get("path")
        if not src:
            return {"status": "error", "error": "track 缺少 url/path"}

        self.stop()   # 先停上一个

        # 在线 URL：先解析成直链（VLC 更稳）
        play_src = src
        if src.startswith(("http://", "https://")) and "youtube" in src:
            play_src = self._resolve_stream_url(src)

        ok = self._spawn(self._build_cmd(play_src))
        if not ok:
            return {"status": "error", "error": "启动播放器失败"}

        self._current_track = track
        self._last_track = track  
        logger.info(f"播放: {track.get('title', '未知')} [{self._player_kind}]")

        return {
            "status": "playing",
            "track": track,
            "player": self._player_kind,
            "message": f"正在播放：{track.get('title', '未知')}",
        }

    def _build_cmd(self, src: str) -> List[str]:
        if self._available_player == "mpv":
            return ["mpv", "--no-video", "--really-quiet",
                    f"--volume={self._volume}", src]
        if self._available_player == "vlc":
            vlc = self._find_vlc()
            vlc_vol = int(self._volume / 100 * 512)
            return [
                vlc,
                "--intf", "dummy",
                "--dummy-quiet",
                "--no-video",
                "--no-video-title-show",
                f"--volume={vlc_vol}",
                src,
            ]
        # system：无进程控制
        if self.system == "Windows":
            return ["cmd", "/c", "start", "", src]
        if self.system == "Darwin":
            return ["open", src]
        return ["xdg-open", src]

    def _spawn(self, cmd: List[str]) -> bool:
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
            self._player_kind = self._available_player
            return True
        except Exception as e:
            logger.error(f"启动失败: {e}")
            self._proc = None
            return False

    def stop(self) -> bool:
        """停止播放（仅 CLI 播放器能停）"""
        if self._is_paused:
            self.resume()
            
        stopped = False
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                stopped = True
            except Exception as e:
                logger.warning(f"停止失败: {e}")
            finally:
                self._proc = None
                self._player_kind = None

        self._current_track = None
        return stopped

    def replay(self) -> Dict[str, Any]:
        """重播上一次播放的曲目（从头开始）"""
        if not self._last_track:
            return {"status": "error", "error": "没有可重播的曲目"}
        return self.play(self._last_track)

    def pause(self) -> bool:
        if self._proc is None or self._is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，无法暂停")
            return False
        try:
            psutil.Process(self._proc.pid).suspend()
            self._is_paused = True
            return True
        except Exception as e:
            logger.error(f"暂停失败: {e}")
            return False

    def resume(self) -> bool:
        if self._proc is None or not self._is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            return False
        try:
            psutil.Process(self._proc.pid).resume()
            self._is_paused = False
            return True
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return False
            
    def set_volume(self, v: int) -> bool:
        """音量 0-100（下次播放生效）"""
        self._volume = max(0, min(100, int(v)))
        logger.info(f"音量设为 {self._volume}（下次播放生效）")
        return True

    # ============================================================
    # 播放列表
    # ============================================================
    def generate_playlist(self, mood: str = "happy", count: int = 10) -> List[Dict[str, Any]]:
        """按情绪抽本地曲目。本地为空则返回空列表。"""
        tracks = self.scan_local()
        if not tracks:
            return []

        styles = self.MOOD_STYLES.get(mood, [])
        hits = [t for t in tracks
                if any(s in t["title"].lower() or s in t["artist"].lower()
                       for s in styles)]

        if len(hits) < count:
            rest = [t for t in tracks if t not in hits]
            random.shuffle(rest)
            hits.extend(rest[: count - len(hits)])

        random.shuffle(hits)
        return hits[:count]

    def save_playlist(self, name: str, tracks: List[Dict[str, Any]]) -> str:
        f = Path(self.config["playlist_dir"]) / f"{name}.json"
        f.write_text(
            json.dumps({"name": name,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "tracks": tracks,
                        "count": len(tracks)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(f)

    def load_playlist(self, name: str) -> Optional[List[Dict[str, Any]]]:
        f = Path(self.config["playlist_dir"]) / f"{name}.json"
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("tracks", [])
        except Exception:
            return None

    # ============================================================
    # 下载
    # ============================================================
    def download(self, query_or_url: str, fmt: str = "mp3") -> Dict[str, Any]:
        """yt-dlp 下载。优先提取 mp3（需要 ffmpeg），失败则保留原格式。"""
        if not YT_DLP_AVAILABLE:
            return {"status": "error", "error": "yt-dlp 未安装"}

        # 如果传的是纯文本，先搜一次拿 URL
        url = query_or_url
        if not query_or_url.startswith(("http://", "https://")):
            hits = self.search_online(query_or_url, limit=1)
            if not hits:
                return {"status": "error", "error": f"未找到: {query_or_url}"}
            url = hits[0]["url"]

        out_dir = Path(self.config["download_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        # 有 ffmpeg 就转 mp3，没有就保留原格式
        has_ffmpeg = shutil.which("ffmpeg") is not None
        if has_ffmpeg:
            postprocessors = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": "192",
            }]
        else:
            postprocessors = []

        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "postprocessors": postprocessors,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            title = info.get("title", "unknown")

            # 扫描输出目录里最新生成的文件
            candidates = sorted(
                out_dir.glob(f"{title}.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            saved = str(candidates[0]) if candidates else ""

            logger.info(f"下载完成: {title} → {saved}")
            self._scan_cache = None   # 让下次扫描能看到新文件
            return {
                "status": "success",
                "title": title,
                "url": url,
                "saved": saved,
                "dir": str(out_dir),
                "converted": bool(postprocessors),
            }
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return {"status": "error", "error": str(e)}

    # ============================================================
    # 状态
    # ============================================================
    def get_status(self) -> Dict[str, Any]:
        return {
            "is_playing": self._proc is not None and self._proc.poll() is None,
            "current_track": self._current_track,
            "player_kind": self._player_kind,
            "available_player": self._available_player,
            "volume": self._volume,
            "playlist_size": len(self._playlist),
            "playlist_index": self._playlist_index,
        }

    # ============================================================
    # execute
    # ============================================================
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        action:
          search    query, [limit]
          play      query | url | track
          stop
          volume    volume
          scan      [refresh]
          playlist  mood, count, [save_name]
          download  query | url, [format]
          status
          lyrics    （占位）
        """
        action = kwargs.get("action", "")
        if not action:
            return {"status": "error", "error": "缺少 action"}

        try:
            # ---- search ----
            if action == "search":
                q = kwargs.get("query", "").strip()
                if not q:
                    return {"status": "error", "error": "search 需要 query"}
                local = self.search_local(q)
                online = [] if local else self.search_online(
                    q, int(kwargs.get("limit", self.config["max_search_results"]))
                )
                return {
                    "status": "success",
                    "result": {
                        "query": q,
                        "local": local[:10],
                        "online": online[:10],
                        "source": "local" if local else ("online" if online else "none"),
                    },
                }

            # ---- play ----
            if action == "play":
                # 优先级：显式 track > url > query
                if kwargs.get("track"):
                    track = kwargs["track"]
                elif kwargs.get("url"):
                    track = {
                        "title": kwargs.get("title", "在线歌曲"),
                        "artist": kwargs.get("artist", "未知"),
                        "url": kwargs["url"],
                    }
                elif kwargs.get("query"):
                    q = kwargs["query"]
                    hits = self.search_local(q)
                    if not hits:
                        hits = self.search_online(q, limit=1)
                    if not hits:
                        return {"status": "error", "error": f"未找到: {q}"}
                    track = hits[0]
                else:
                    return {"status": "error", "error": "play 需要 query/url/track"}

                r = self.play(track)
                return {"status": "success" if r["status"] == "playing" else "error",
                        "result": r}

            # ---- stop ----
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
                        
            # ---- volume ----
            if action == "volume":
                v = kwargs.get("volume")
                if v is None:
                    return {"status": "success", "result": {"volume": self._volume}}
                self.set_volume(v)
                return {"status": "success", "result": {"volume": self._volume}}

            # ---- scan ----
            if action == "scan":
                tracks = self.scan_local(refresh=bool(kwargs.get("refresh")))
                return {"status": "success",
                        "result": {"total": len(tracks),
                                   "tracks": tracks[:50]}}

            # ---- playlist ----
            if action == "playlist":
                mood = kwargs.get("mood", "happy")
                count = int(kwargs.get("count", 10))
                tracks = self.generate_playlist(mood, count)
                out = {"mood": mood, "tracks": tracks, "count": len(tracks)}
                if kwargs.get("save_name"):
                    out["saved"] = self.save_playlist(kwargs["save_name"], tracks)
                return {"status": "success", "result": out}

            # ---- download ----
            if action == "download":
                src = kwargs.get("query") or kwargs.get("url")
                if not src:
                    return {"status": "error", "error": "download 需要 query/url"}
                r = self.download(src, fmt=kwargs.get("format", "mp3"))
                return {"status": "success" if r["status"] == "success" else "error",
                        "result": r,
                        "error": r.get("error")}

            # ---- status ----
            if action == "status":
                return {"status": "success", "result": self.get_status()}

            return {"status": "error", "error": f"未知操作: {action}"}

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<MusicPlayer v{self.version} player={self._available_player}>"