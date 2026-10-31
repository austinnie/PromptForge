"""
social_auto_upload - 多平台内容分发 Skill（P2 补齐版）

架构：
  本 skill 不直接实现上传逻辑，而是 subprocess 调用 social-auto-upload
  项目的 sau_cli.py。

  sau_cli.py 位置探测顺序：
    1. skills/social_auto_upload/sau_cli.py         （内嵌）
    2. skills/social_auto_upload/social-auto-upload/sau_cli.py （子目录）
    3. <project_root>/social-auto-upload/sau_cli.py （项目根）
    4. PATH 里的 sau / sau_cli                       （全局安装）

  找不到 sau_cli.py 时：dry_run 模式仍可用（打印命令），真实调用返回提示。

支持平台：
  - 视频：douyin, kuaishou, xiaohongshu, bilibili, tencent, weibo, youtube, ...
  - 图文：douyin, kuaishou, xiaohongshu

安装指引（首次使用时）：
    git clone https://github.com/dreammis/social-auto-upload.git \\
      skills/social_auto_upload/social-auto-upload
    cd skills/social_auto_upload/social-auto-upload
    pip install -r requirements.txt
    playwright install chromium

依赖：
  - Python 3.10+
  - social-auto-upload（git clone）
  - Playwright chromium（sau 内部用）
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 平台常量
# ============================================================

SUPPORTED_PLATFORMS = [
    "douyin",        # 抖音
    "kuaishou",      # 快手
    "xiaohongshu",   # 小红书
    "bilibili",      # B站
    "tencent",       # 视频号
    "weibo",         # 微博
    "hupu",          # 虎扑
    "youtube",       # YouTube
    "alipay",        # 支付宝生活号
]

NOTE_PLATFORMS = ["douyin", "kuaishou", "xiaohongshu"]           # 图文
SCHEDULE_PLATFORMS = ["douyin", "kuaishou", "xiaohongshu", "bilibili", "tencent"]

PLATFORM_NAMES = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
    "tencent": "视频号",
    "weibo": "微博",
    "hupu": "虎扑",
    "youtube": "YouTube",
    "alipay": "支付宝",
}


# ============================================================
# Skill
# ============================================================

class SocialAutoUpload:
    name = "social_auto_upload"
    version = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self._sau_path: Optional[Path] = None
        self._locate_sau()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "timeout": 300,           # subprocess 超时（秒）
            "auto_confirm": True,      # 自动 --yes
            "dry_run": False,          # 只打印命令
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    def _locate_sau(self) -> Optional[Path]:
        """定位 sau_cli.py 或 sau 可执行文件。"""
        skill_dir = Path(__file__).parent
        project_root = Path(__file__).resolve().parents[2]

        # 1. 内嵌 / 子目录 / 项目根 三种候选
        candidates = [
            skill_dir / "sau_cli.py",
            skill_dir / "social-auto-upload" / "sau_cli.py",
            project_root / "social-auto-upload" / "sau_cli.py",
            skill_dir / "sau",
            skill_dir / "sau.exe",
        ]
        for p in candidates:
            if p.exists():
                self._sau_path = p
                logger.info(f"✅ 找到 sau_cli: {p}")
                return p

        # 2. PATH 里的 sau / sau_cli
        for name in ("sau", "sau_cli", "sau.exe", "sau_cli.exe"):
            which = shutil.which(name)
            if which:
                self._sau_path = Path(which)
                logger.info(f"✅ 找到 sau（PATH）: {which}")
                return self._sau_path

        logger.warning("⚠️ 未找到 sau_cli.py（安装指引见 skill 文档）")
        self._sau_path = None
        return None

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """dispatch: action=publish_video / publish_note / login / check / list_platforms

        关键 kwargs：
          action:        publish_video（默认）
          platform:      douyin / kuaishou / ...
          file:          视频路径（publish_video 必需）
          images:        图片路径列表（publish_note 必需）
          title:         标题
          desc:          描述
          tags:          标签列表
          account:       账号名（sau 内部用）
          schedule:      定时发布 "2026-10-31 20:00"
          thumbnail:     封面图路径
          dry_run:       只打印命令
        """
        action = kwargs.get("action", "publish_video")

        if action == "list_platforms":
            return self._list_platforms()

        if action == "publish_video":
            return self._publish_video(kwargs)

        if action == "publish_note":
            return self._publish_note(kwargs)

        if action == "login":
            return self._login(kwargs)

        if action == "check":
            return self._check(kwargs)

        return {"status": "error", "error": f"不支持 action: {action}"}

    # ---------- list_platforms ----------

    def _list_platforms(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "result": {
                "all": SUPPORTED_PLATFORMS,
                "note": NOTE_PLATFORMS,
                "schedule": SCHEDULE_PLATFORMS,
                "names": PLATFORM_NAMES,
                "sau_available": self._sau_path is not None,
                "sau_path": str(self._sau_path) if self._sau_path else None,
            },
        }

    # ---------- publish_video ----------

    def _publish_video(self, kwargs) -> Dict[str, Any]:
        platform = (kwargs.get("platform") or "").lower()
        file_path = kwargs.get("file") or ""
        title = (kwargs.get("title") or "").strip()
        desc = kwargs.get("desc", "") or ""
        tags = kwargs.get("tags") or []
        account = kwargs.get("account")
        schedule = kwargs.get("schedule")
        thumbnail = kwargs.get("thumbnail")
        dry_run = bool(kwargs.get("dry_run", self.config["dry_run"]))

        if not platform:
            return {"status": "error", "error": "platform 不能为空"}
        if platform not in SUPPORTED_PLATFORMS:
            return {
                "status": "error",
                "error": f"不支持的平台: {platform}。支持: {SUPPORTED_PLATFORMS}",
            }
        if not file_path or not Path(file_path).exists():
            return {"status": "error", "error": f"视频文件不存在: {file_path}"}
        if not title:
            return {"status": "error", "error": "title 不能为空"}

        # 构造命令
        cmd = self._build_base_cmd() + [
            "video", platform,
            "--file", str(file_path),
            "--title", title,
        ]
        if desc:
            cmd.extend(["--desc", desc])
        if tags:
            cmd.extend(["--tags", ",".join(tags) if isinstance(tags, list) else tags])
        if account:
            cmd.extend(["--account", account])
        if schedule:
            if platform not in SCHEDULE_PLATFORMS:
                logger.warning(f"{platform} 不支持定时发布，忽略 schedule")
            else:
                cmd.extend(["--schedule", schedule])
        if thumbnail and Path(thumbnail).exists():
            cmd.extend(["--thumbnail", str(thumbnail)])

        return self._run(cmd, dry_run=dry_run)

    # ---------- publish_note ----------

    def _publish_note(self, kwargs) -> Dict[str, Any]:
        platform = (kwargs.get("platform") or "").lower()
        images = kwargs.get("images") or []
        title = (kwargs.get("title") or "").strip()
        note = kwargs.get("note", "") or ""
        tags = kwargs.get("tags") or []
        account = kwargs.get("account")
        schedule = kwargs.get("schedule")
        dry_run = bool(kwargs.get("dry_run", self.config["dry_run"]))

        if not platform:
            return {"status": "error", "error": "platform 不能为空"}
        if platform not in NOTE_PLATFORMS:
            return {
                "status": "error",
                "error": f"{platform} 不支持图文。支持: {NOTE_PLATFORMS}",
            }
        if not images:
            return {"status": "error", "error": "images 不能为空"}
        missing = [p for p in images if not Path(p).exists()]
        if missing:
            return {"status": "error", "error": f"图片不存在: {missing}"}
        if not title:
            return {"status": "error", "error": "title 不能为空"}

        cmd = self._build_base_cmd() + [
            "note", platform,
            "--images", *[str(p) for p in images],
            "--title", title,
        ]
        if note:
            cmd.extend(["--note", note])
        if tags:
            cmd.extend(["--tags", ",".join(tags) if isinstance(tags, list) else tags])
        if account:
            cmd.extend(["--account", account])
        if schedule and platform in SCHEDULE_PLATFORMS:
            cmd.extend(["--schedule", schedule])

        return self._run(cmd, dry_run=dry_run)

    # ---------- login ----------

    def _login(self, kwargs) -> Dict[str, Any]:
        platform = (kwargs.get("platform") or "").lower()
        account = kwargs.get("account")
        dry_run = bool(kwargs.get("dry_run", self.config["dry_run"]))

        if not platform:
            return {"status": "error", "error": "platform 不能为空"}
        if platform not in SUPPORTED_PLATFORMS:
            return {"status": "error", "error": f"不支持的平台: {platform}"}

        cmd = self._build_base_cmd() + ["login", platform]
        if account:
            cmd.extend(["--account", account])

        result = self._run(cmd, dry_run=dry_run)

        if result.get("status") == "success" and not dry_run:
            # 提示用户：sau 会在终端弹二维码
            result["hint"] = (
                "sau 会在终端显示二维码，请用对应平台 App 扫码。"
                "登录态会保存到 sau 的本地存储，下次不用重复扫码。"
            )
        return result

    # ---------- check ----------

    def _check(self, kwargs) -> Dict[str, Any]:
        platform = (kwargs.get("platform") or "").lower()
        account = kwargs.get("account")
        dry_run = bool(kwargs.get("dry_run", self.config["dry_run"]))

        if not platform:
            return {"status": "error", "error": "platform 不能为空"}

        cmd = self._build_base_cmd() + ["check", platform]
        if account:
            cmd.extend(["--account", account])

        return self._run(cmd, dry_run=dry_run)

    # ---------- 内部 ----------

    def _build_base_cmd(self) -> List[str]:
        """构造命令行前缀。"""
        if self._sau_path is None:
            # 给一个占位命令（dry_run 用）
            return ["sau"]
        p = self._sau_path
        # 是 .py 文件 → 用 python 跑
        if p.suffix == ".py":
            return [sys.executable, str(p)]
        # 是可执行文件 → 直接跑
        return [str(p)]

    def _run(self, cmd: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """执行命令 / 或 dry_run 打印。"""
        # 自动加 --yes（避免交互）
        if self.config["auto_confirm"] and "--yes" not in cmd:
            cmd = cmd + ["--yes"]

        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)

        # dry_run 或 sau 缺失 → 只打印
        if dry_run or self._sau_path is None:
            reason = "dry_run 模式" if dry_run else "sau_cli 未找到"
            return {
                "status": "success",
                "result": {
                    "dry_run": True,
                    "reason": reason,
                    "cmd": cmd,
                    "cmd_str": cmd_str,
                    "hint": (
                        "这是 dry_run 输出，命令没有真正执行。"
                        if dry_run else
                        "sau_cli.py 未找到，未执行。安装方法：\n"
                        "  git clone https://github.com/dreammis/social-auto-upload.git "
                        "skills/social_auto_upload/social-auto-upload\n"
                        "  cd skills/social_auto_upload/social-auto-upload\n"
                        "  pip install -r requirements.txt\n"
                        "  playwright install chromium"
                    ),
                },
            }

        # 真正执行
        try:
            logger.info(f"▶️ 执行: {cmd_str[:200]}")
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config["timeout"],
                encoding="utf-8",
                errors="replace",
            )
            stdout = (r.stdout or "").strip()
            stderr = (r.stderr or "").strip()

            if r.returncode != 0:
                return {
                    "status": "error",
                    "error": self._extract_error(stderr or stdout) or f"exit {r.returncode}",
                    "result": {
                        "cmd": cmd,
                        "returncode": r.returncode,
                        "stdout": stdout[-2000:],
                        "stderr": stderr[-2000:],
                    },
                }

            return {
                "status": "success",
                "result": {
                    "dry_run": False,
                    "cmd": cmd,
                    "returncode": 0,
                    "stdout": stdout[-2000:],
                    "stderr": stderr[-2000:],
                    "executed_at": datetime.now().isoformat(),
                },
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"命令超时（>{self.config['timeout']}s）",
                "result": {"cmd": cmd},
            }
        except Exception as e:
            logger.exception("subprocess 执行失败")
            return {"status": "error", "error": str(e), "result": {"cmd": cmd}}

    @staticmethod
    def _extract_error(text: str) -> str:
        """从 sau 输出里抓关键错误行。"""
        if not text:
            return ""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        # 优先找含 "error" / "❌" / "failed" / "失败" 的行
        for line in lines:
            low = line.lower()
            if any(kw in low for kw in ("error", "failed", "失败", "❌", "exception")):
                return line[:300]
        # 否则取最后一行
        return lines[-1][:300] if lines else ""

    # ---------- 展示 ----------

    def get_name(self) -> str:
        if self._sau_path:
            return "SocialAutoUpload (sau 就绪)"
        return "SocialAutoUpload (sau 未安装，dry_run only)"

    def __repr__(self):
        return f"<SocialAutoUpload(sau={self._sau_path})>"