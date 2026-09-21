"""
radio_player - 网络广播播放器

优化点（v2）：
  - 优先使用 mpv / ffplay / vlc（可跟踪进程、可调音量）
  - VLC 自动探测 Windows / macOS / Linux 常见安装路径
  - 回退到系统默认程序或浏览器（仅能播放，无控制）
  - 收藏持久化到 output/radio_player/favorites.json
  - 与 PromptForge 其他 skill 一致的 execute() 返回结构
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import signal
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
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    
class RadioPlayer:
    """网络广播播放器"""

    name = "radio_player"
    version = "2.0.0"

    # ============================================================
    # 电台库
    # ============================================================
    DEFAULT_STATIONS: Dict[str, Dict[str, str]] = {
        "japan": {
            "NHK-FM":     "https://radio-stream.nhk.jp/hls/nhkradioruak/now/1.m3u8",
            "NHK-R1":     "https://radio-stream.nhk.jp/hls/nhkradior1/now/1.m3u8",
            "NHK-R2":     "https://radio-stream.nhk.jp/hls/nhkradior2/now/1.m3u8",
            # radiko / J-WAVE / Tokyo FM 是网页播放器（需 Flash/JS 环境），
            # 走浏览器打开，不进入流媒体播放器路径
            "TBS Radio（网页）":           "https://radiko.jp/#!/live/TBS",
            "Nippon Broadcasting（网页）": "https://radiko.jp/#!/live/QRR",
            "J-WAVE（网页）":              "https://www.j-wave.co.jp/player/player.html",
            "Tokyo FM（网页）":            "https://www.tfm.co.jp/player/",
            "FM802（网页）":               "https://radiko.jp/#!/live/FM802",
            "FM Yokohama（网页）":         "https://radiko.jp/#!/live/YFM",
            "InterFM（网页）":             "https://radiko.jp/#!/live/INT",
            "RN1（网页）":                 "https://radiko.jp/#!/live/RN1",
            "日经CNBC（网页）":            "https://www.nikkei-cnbc.co.jp/",
            "Bloomberg Japan（网页）":     "https://www.bloomberg.co.jp/radio/",
        },
        "china": {
            "中国之声":       "http://ngcdn001.cnr.cn/live/zgzs/index.m3u8",
            "经济之声":       "http://ngcdn001.cnr.cn/live/jjzs/index.m3u8",
            "音乐之声":       "http://ngcdn001.cnr.cn/live/yyzs/index.m3u8",
            "都市之声":       "http://ngcdn001.cnr.cn/live/dszs/index.m3u8",
            "中华之声":       "http://ngcdn001.cnr.cn/live/zhzs/index.m3u8",
            "华夏之声":       "http://ngcdn001.cnr.cn/live/hxzs/index.m3u8",
            "文艺之声":       "http://ngcdn001.cnr.cn/live/wyzs/index.m3u8",
            "经典音乐广播":   "http://ngcdn001.cnr.cn/live/jdyy/index.m3u8",
            "大湾区之声":     "http://ngcdn001.cnr.cn/live/dwqzs/index.m3u8",
            "香港电台第一台": "https://rthkaudio1-lh.akamaihd.net/i/radio1_1@355841/master.m3u8",
            "香港电台第二台": "https://rthkaudio2-lh.akamaihd.net/i/radio2_1@355842/master.m3u8",
            "香港电台第三台": "https://rthkaudio3-lh.akamaihd.net/i/radio3_1@355843/master.m3u8",
            "香港电台第四台": "https://rthkaudio4-lh.akamaihd.net/i/radio4_1@355844/master.m3u8",
        },
        "korea": {
            "KBS 1FM":      "http://kbsradio-stream.akamaized.net/hls/live/2040613/KBSRADIO_1FM/playlist.m3u8",
            "KBS 2FM":      "http://kbsradio-stream.akamaized.net/hls/live/2040614/KBSRADIO_2FM/playlist.m3u8",
            "MBC FM4U":     "http://mbcradio-stream.akamaized.net/hls/live/2040615/MBCRADIO_FM4U/playlist.m3u8",
            "SBS Power FM": "http://sbsradio-stream.akamaized.net/hls/live/2040616/SBSRADIO_POWERFM/playlist.m3u8",
            "EBS FM":       "https://ebsradio-stream.akamaized.net/hls/live/2040617/EBSRADIO_FM/playlist.m3u8",
        },
        "international": {
            "BBC World Service": "http://bbcwssc.ic.llnwd.net/stream/bbcwssc_mp1_ws-eieuk",
            "BBC Radio 1":       "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
            "BBC Radio 2":       "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two",
            "BBC Radio 3":       "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_three",
            "BBC Radio 4":       "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_fourfm",
            "BBC Radio 5 Live":  "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_five_live",
            "NPR":               "https://npr-ice.streamguys1.com/live.mp3",
            "Voice of America":  "https://voa-news.akamaized.net/hls/live/2034963/voanews/playlist.m3u8",
            "Deutsche Welle":    "http://dw-radio.streamguys1.com/dw-rus",
            "Radio France":      "https://direct.franceinter.fr/live/franceinter-midfi.mp3",
        },
        "music": {
            "Classical FM": "https://stream.radioplayer.co.uk/classicfm",
            "Jazz FM":      "https://stream.radioplayer.co.uk/jazzfm",
            "Smooth FM":    "https://stream.radioplayer.co.uk/smooth",
            "Heart FM":     "https://stream.radioplayer.co.uk/heart",
            "Capital FM":   "https://stream.radioplayer.co.uk/capital",
        },
        "web": {
            "Radio Garden":    "https://radio.garden/",
            "TuneIn Radio":    "https://tunein.com/",
            "myTuner Radio":   "https://mytuner-radio.com/",
            "LiveOnlineRadio": "https://www.liveonlineradio.net/",
        },
    }

    CATEGORY_NAMES = {
        "japan":         "🇯🇵 日本电台",
        "china":         "🇨🇳 中国电台",
        "korea":         "🇰🇷 韩国电台",
        "international": "🌍 国际电台",
        "music":         "🎵 音乐电台",
        "web":           "🌐 网页电台",
    }

    # ============================================================
    # 播放器路径（Windows 常见安装位置）
    # ============================================================
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
        self.current_station: Optional[Dict[str, Any]] = None
        self._last_station: Optional[Dict[str, Any]] = None
        self.is_playing = False
        self.is_paused = False
        self.volume = int(self.config["default_volume"])

        # 播放器进程
        self._proc: Optional[subprocess.Popen] = None
        self._player_kind: Optional[str] = None   # mpv / ffplay / vlc / system / browser
        self.system = platform.system()

        # 探测可用 CLI 播放器（只做一次）
        self._available_player = self._detect_player()

        # 收藏
        self.favorites: List[str] = []
        self._load_favorites()

        # 启动日志
        player_path = ""
        if self._available_player == "vlc":
            player_path = f" @ {self._find_vlc()}"
        elif self._available_player in ("mpv", "ffplay"):
            player_path = f" @ {shutil.which(self._available_player)}"
        logger.info(
            f"RadioPlayer v{self.version} 就绪 "
            f"(系统={self.system}, 播放器={self._available_player}{player_path})"
        )

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "default_volume": 80,
            "default_category": "china",
            "default_station": "中国之声",
            "output_dir": str(PROJECT_ROOT / "output" / "radio_player"),
            "favorites_file": "favorites.json",
            "log_level": "INFO",
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 播放器探测
    # ============================================================
    def _find_vlc(self) -> Optional[str]:
        """返回 vlc / cvlc 可执行文件的绝对路径，找不到返回 None"""
        # 1) PATH 里找（Linux / macOS 常见）
        for name in ("cvlc", "vlc"):
            p = shutil.which(name)
            if p:
                return p
        # 2) Windows 常见安装路径
        if self.system == "Windows":
            for path in self._VLC_WIN_PATHS:
                if Path(path).exists():
                    return path
        # 3) macOS 应用包内
        if self.system == "Darwin":
            mac_vlc = "/Applications/VLC.app/Contents/MacOS/VLC"
            if Path(mac_vlc).exists():
                return mac_vlc
        return None

    def _detect_player(self) -> str:
        """返回 'mpv' | 'ffplay' | 'vlc' | 'system'（按优先级）"""
        if shutil.which("mpv"):
            return "mpv"
        if shutil.which("ffplay"):
            return "ffplay"
        if self._find_vlc():
            return "vlc"
        return "system"

    def _is_web_url(self, url: str) -> bool:
        """判断是否为网页播放器（需要浏览器 JS 环境）"""
        web_hints = (
            ".html", ".htm",
            "radiko.jp", "j-wave.co.jp", "tfm.co.jp",
            "radio.garden", "tunein.com",
            "mytuner-radio.com", "liveonlineradio.net",
            "nikkei-cnbc.co.jp", "bloomberg.co.jp",
        )
        u = url.lower()
        return any(h in u for h in web_hints)

    # ============================================================
    # 收藏
    # ============================================================
    def _favorites_path(self) -> Path:
        return Path(self.config["output_dir"]) / self.config["favorites_file"]

    def _load_favorites(self):
        p = self._favorites_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.favorites = [str(x) for x in data]
                logger.info(f"加载收藏: {len(self.favorites)} 个")
        except Exception as e:
            logger.warning(f"读取收藏失败: {e}")

    def _save_favorites(self):
        p = self._favorites_path()
        try:
            p.write_text(
                json.dumps(self.favorites, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"保存收藏: {len(self.favorites)} 个")
        except Exception as e:
            logger.error(f"保存收藏失败: {e}")

    # ============================================================
    # 电台查询
    # ============================================================
    def get_categories(self) -> List[str]:
        return list(self.DEFAULT_STATIONS.keys())

    def get_stations(self, category: Optional[str] = None) -> Dict[str, str]:
        if category:
            return dict(self.DEFAULT_STATIONS.get(category, {}))
        merged: Dict[str, str] = {}
        for stations in self.DEFAULT_STATIONS.values():
            merged.update(stations)
        return merged

    def list_stations(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        cats = [category] if category else self.get_categories()
        out: List[Dict[str, Any]] = []
        for cat in cats:
            for name, url in self.DEFAULT_STATIONS.get(cat, {}).items():
                out.append({
                    "name": name,
                    "url": url,
                    "category": cat,
                    "category_name": self.CATEGORY_NAMES.get(cat, cat),
                    "favorite": name in self.favorites,
                    "is_web": self._is_web_url(url),
                })
        return out

    def search_station(self, keyword: str) -> Dict[str, str]:
        kw = keyword.lower()
        results: Dict[str, str] = {}
        for cat, stations in self.DEFAULT_STATIONS.items():
            if kw in cat.lower():
                results.update(stations)
                continue
            for name, url in stations.items():
                if kw in name.lower():
                    results[name] = url
        return results

    # ============================================================
    # 播放核心
    # ============================================================
    def _spawn(self, cmd: List[str]) -> bool:
        """启动播放器进程（不阻塞）"""
        try:
            creationflags = 0
            if self.system == "Windows":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            return True
        except Exception as e:
            logger.error(f"启动播放器失败: {e}")
            self._proc = None
            return False

    def _play_stream(self, url: str) -> bool:
        """播放流媒体 URL（走 CLI 播放器）"""
        player = self._available_player

        if player == "mpv":
            cmd = ["mpv", "--no-video", "--really-quiet",
                   f"--volume={self.volume}", url]

        elif player == "ffplay":
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                   "-volume", str(self.volume), url]

        elif player == "vlc":
            vlc_exe = self._find_vlc()
            if not vlc_exe:
                logger.warning("VLC 未找到，回退系统播放器")
                return self._play_stream_with_system(url)
            # VLC 音量 0-512，80% → 410
            vlc_vol = int(self.volume / 100 * 512)
            cmd = [
                vlc_exe,
                "--intf", "dummy",
                "--dummy-quiet",
                "--no-video",
                "--no-video-title-show",
                f"--volume={vlc_vol}",
                url,
            ]

        else:
            return self._play_stream_with_system(url)

        ok = self._spawn(cmd)
        self._player_kind = player if ok else None
        return ok

    def _play_stream_with_system(self, url: str) -> bool:
        """回退：系统默认程序打开 URL（无进程控制）"""
        try:
            if self.system == "Windows":
                os.startfile(url)
            elif self.system == "Darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
            self._player_kind = "system"
            return True
        except Exception as e:
            logger.error(f"系统播放器失败: {e}")
            return False

    def _play_in_browser(self, url: str) -> bool:
        try:
            webbrowser.open(url)
            self._player_kind = "browser"
            return True
        except Exception as e:
            logger.error(f"浏览器打开失败: {e}")
            return False

    def play(
        self,
        station_name: Optional[str] = None,
        category: Optional[str] = None,
        url: Optional[str] = None,
    ) -> bool:
        """播放电台"""
        self.stop()

        if url:
            return self._play_url(url, station_name or "自定义电台")

        if station_name:
            if category:
                stations = self.DEFAULT_STATIONS.get(category, {})
                if station_name in stations:
                    return self._play_url(stations[station_name], station_name)

            for stations in self.DEFAULT_STATIONS.values():
                if station_name in stations:
                    return self._play_url(stations[station_name], station_name)

            hits = self.search_station(station_name)
            if hits:
                first = next(iter(hits))
                return self._play_url(hits[first], first)

            logger.warning(f"未找到电台: {station_name}")
            return False

        cat = category or self.config["default_category"]
        name = self.config["default_station"]
        stations = self.DEFAULT_STATIONS.get(cat, {})
        if name in stations:
            return self._play_url(stations[name], name)
        if stations:
            first = next(iter(stations))
            return self._play_url(stations[first], first)
        return False

    def _play_url(self, url: str, name: str) -> bool:
        self.current_station = {
            "name": name,
            "url": url,
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._last_station = dict(self.current_station)
        logger.info(f"播放: {name} ({url})")

        if self._is_web_url(url):
            logger.info("检测到网页播放器 → 浏览器打开")
            ok = self._play_in_browser(url)
        else:
            ok = self._play_stream(url)

        self.is_playing = ok
        self.is_paused = False
        return ok

    # ============================================================
    # 控制
    # ============================================================
    def stop(self) -> bool:
        """停止播放（仅 CLI 播放器可停）"""
        if self.is_paused:
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
                logger.warning(f"停止播放器失败: {e}")
            finally:
                self._proc = None

        self.is_playing = False
        self.is_paused = False
        self._player_kind = None
        self.current_station = None 
        return stopped

    def replay(self) -> bool:
        """重播上一次播放的电台"""
        if not self._last_station:
            return False
        s = self._last_station
        return self._play_url(s["url"], s["name"])
        
    def pause(self) -> bool:
        if self._proc is None or self.is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，无法暂停")
            return False
        try:
            psutil.Process(self._proc.pid).suspend()
            self.is_paused = True
            logger.info("已暂停")
            return True
        except Exception as e:
            logger.error(f"暂停失败: {e}")
            return False

    def resume(self) -> bool:
        if self._proc is None or not self.is_paused:
            return False
        if not PSUTIL_AVAILABLE:
            return False
        try:
            psutil.Process(self._proc.pid).resume()
            self.is_paused = False
            logger.info("已继续")
            return True
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return False

    def set_volume(self, volume: int) -> bool:
        """设置音量（仅对下一次播放生效）"""
        self.volume = max(0, min(100, int(volume)))
        logger.info(f"音量设为 {self.volume}（下次播放生效）")
        return True

    # ============================================================
    # 收藏
    # ============================================================
    def toggle_favorite(self, station_name: str) -> bool:
        if station_name in self.favorites:
            self.favorites.remove(station_name)
            self._save_favorites()
            return False
        self.favorites.append(station_name)
        self._save_favorites()
        return True

    def get_favorites(self) -> List[str]:
        return list(self.favorites)

    # ============================================================
    # 状态
    # ============================================================
    def get_status(self) -> Dict[str, Any]:
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "volume": self.volume,
            "current_station": self.current_station,
            "player_kind": self._player_kind,
            "available_player": self._available_player,
            "favorites_count": len(self.favorites),
        }

    # ============================================================
    # execute 入口
    # ============================================================
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        action:
          play | stop | pause | resume | status | list | search
          | favorite | favorites | volume
        """
        action = kwargs.get("action", "play")
        logger.info(f"执行技能: {self.name} (v{self.version}) action={action}")

        try:
            if action == "play":
                ok = self.play(
                    station_name=kwargs.get("station"),
                    category=kwargs.get("category"),
                    url=kwargs.get("url"),
                )
                if not ok:
                    return {"status": "error",
                            "error": f"无法播放: {kwargs.get('station') or '默认电台'}"}
                return {
                    "status": "success",
                    "result": {
                        "action": "play",
                        "station": self.current_station,
                        "player": self._player_kind,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                    },
                }

            if action == "stop":
                self.stop()
                return {"status": "success",
                        "result": {"action": "stop", "stopped": True}}

            if action == "replay":
                ok = self.replay()
                return {
                    "status": "success" if ok else "error",
                    "result": {
                        "action": "replay",
                        "station": self.current_station,
                        "player": self._player_kind,
                    },
                    "error": None if ok else "没有可重播的电台",
                }
                
            if action == "pause":
                paused = self.is_paused
                if paused:
                    self.resume()
                else:
                    self.pause()
                return {"status": "success",
                        "result": {"action": "pause", "is_paused": self.is_paused}}

            if action == "status":
                return {"status": "success", "result": self.get_status()}

            if action == "list":
                category = kwargs.get("category")
                stations = self.list_stations(category)
                return {"status": "success",
                        "result": {"stations": stations, "count": len(stations)}}

            if action == "search":
                kw = kwargs.get("keyword")
                if not kw:
                    return {"status": "error", "error": "请提供 keyword"}
                hits = self.search_station(kw)
                return {"status": "success",
                        "result": {"keyword": kw, "results": hits, "count": len(hits)}}

            if action == "favorite":
                name = kwargs.get("station")
                if not name:
                    return {"status": "error", "error": "请提供 station"}
                is_fav = self.toggle_favorite(name)
                return {"status": "success",
                        "result": {"station": name,
                                   "is_favorite": is_fav,
                                   "favorites": self.favorites}}

            if action == "favorites":
                return {"status": "success",
                        "result": {"favorites": self.favorites,
                                   "count": len(self.favorites)}}

            if action == "volume":
                v = kwargs.get("volume")
                if v is not None:
                    self.set_volume(v)
                return {"status": "success",
                        "result": {"volume": self.volume}}

            return {"status": "error", "error": f"未知操作: {action}"}

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def __repr__(self):
        return f"<RadioPlayer v{self.version} player={self._available_player}>"