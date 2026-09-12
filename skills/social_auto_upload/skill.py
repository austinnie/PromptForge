"""
social_auto_upload - 多平台内容分发 Skill

内嵌 social-auto-upload，通过 subprocess 调用其 sau_cli.py
把 PromptForge 生成的视频/图片分发到各社交平台。
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = [
    "douyin", "kuaishou", "xiaohongshu", "bilibili",
    "tencent", "alipay", "weibo", "hupu", "youtube", "baijiahao",
]

NOTE_PLATFORMS = ["douyin", "kuaishou", "xiaohongshu"]

SCHEDULE_PLATFORMS = [
    "douyin", "kuaishou", "xiaohongshu", "bilibili", "tencent",
]


class SocialAutoUpload:
    """多平台内容分发"""

    name = "social_auto_upload"
    version = "1.0.0"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
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
            "sau_python": None,          # 指定 python（默认 sys.executable）
            "default_account": "test",
            "timeout_video": 900,        # 视频上传超时（秒）
            "timeout_note": 300,         # 图文上传
            "timeout_login": 600,        # 扫码登录
            "timeout_check": 120,        # 账号校验
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    def _locate_sau(self):
        """定位本技能内的 sau_cli.py"""
        # 本文件在 skills/social_auto_upload/skill.py
        root = Path(__file__).resolve().parent
        if (root / "sau_cli.py").exists():
            self._sau_root = root
            logger.info(f"✅ social-auto-upload 内嵌: {self._sau_root}")
        else:
            self._sau_root = None
            logger.warning(f"⚠️ 未找到 sau_cli.py，检查目录: {root}")

    # ---------- 底层执行 ----------

    def _run(self, args: List[str], timeout: int) -> Dict[str, Any]:
        if not self._sau_root:
            return {"status": "error", "error": "未找到 sau_cli.py"}

        python = self.config.get("sau_python") or sys.executable
        cmd = [python, str(self._sau_root / "sau_cli.py"), *args]
        logger.info(f"▶ {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._sau_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"执行超时（>{timeout}s）"}
        except Exception as e:
            return {"status": "error", "error": f"执行异常: {e}"}

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # 实时回显 sau 的输出
        for line in stdout.splitlines():
            if line.strip():
                logger.info(f"  [sau] {line.strip()}")
        for line in stderr.splitlines():
            if line.strip():
                logger.warning(f"  [sau:err] {line.strip()}")

        if result.returncode != 0:
            return {
                "status": "error",
                "error": self._extract_error(stdout + stderr),
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

        return {"status": "success", "stdout": stdout, "stderr": stderr}

    @staticmethod
    def _extract_error(text: str) -> str:
        """从 sau 输出里抓关键错误行"""
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if "ERROR" in s or "错误" in s or "失败" in s or "Error:" in s:
                return s
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines[-1] if lines else "未知错误"

    # ---------- 公开 API ----------

    def login(self, platform: str, account: str = None) -> Dict[str, Any]:
        """登录指定平台（弹浏览器/终端二维码）"""
        if platform not in SUPPORTED_PLATFORMS:
            return {"status": "error", "error": f"不支持的平台: {platform}"}
        account = account or self.config["default_account"]
        return self._run(
            [platform, "login", "--account", account],
            timeout=self.config["timeout_login"],
        )

    def check(self, platform: str, account: str = None) -> Dict[str, Any]:
        """校验账号登录态"""
        if platform not in SUPPORTED_PLATFORMS:
            return {"status": "error", "error": f"不支持的平台: {platform}"}
        account = account or self.config["default_account"]
        result = self._run(
            [platform, "check", "--account", account],
            timeout=self.config["timeout_check"],
        )
        # sau 输出就是一行 "valid" 或 "invalid"
        stdout = (result.get("stdout") or "").strip()
        last_line = stdout.splitlines()[-1].strip().lower() if stdout else ""
        result["valid"] = (last_line == "valid")
        return result

    def publish_video(
        self,
        platform: str,
        file: str,
        title: str,
        desc: str = "",
        tags: Optional[List[str]] = None,
        account: str = None,
        schedule: str = None,
        thumbnail: str = None,
        tid: int = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """上传视频到指定平台"""
        if platform not in SUPPORTED_PLATFORMS:
            return {"status": "error", "error": f"不支持的平台: {platform}"}

        file_path = Path(file).resolve()
        if not file_path.exists():
            return {"status": "error", "error": f"文件不存在: {file_path}"}

        account = account or self.config["default_account"]
        args = [
            platform, "upload-video",
            "--account", account,
            "--file", str(file_path),
            "--title", title,
        ]
        if desc:
            args += ["--desc", desc]
        if tags:
            tag_str = ",".join(tags) if isinstance(tags, list) else str(tags)
            args += ["--tags", tag_str]
        if schedule and platform in SCHEDULE_PLATFORMS:
            args += ["--schedule", schedule]
        if thumbnail:
            args += ["--thumbnail", str(Path(thumbnail).resolve())]
        if tid is not None and platform == "bilibili":
            args += ["--tid", str(tid)]

        result = self._run(args, timeout=self.config["timeout_video"])
        result.update({"platform": platform, "file": str(file_path)})
        return result

    def publish_note(
        self,
        platform: str,
        images: List[str],
        title: str,
        note: str = "",
        tags: Optional[List[str]] = None,
        account: str = None,
        schedule: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """上传图文（仅 douyin/kuaishou/xiaohongshu 支持）"""
        if platform not in NOTE_PLATFORMS:
            return {
                "status": "error",
                "error": f"{platform} 不支持图文，仅支持: {NOTE_PLATFORMS}",
            }

        if isinstance(images, str):
            images = [images]
        image_paths = [str(Path(p).resolve()) for p in images]
        missing = [p for p in image_paths if not Path(p).exists()]
        if missing:
            return {"status": "error", "error": f"图片不存在: {missing}"}

        account = account or self.config["default_account"]
        args = [
            platform, "upload-note",
            "--account", account,
            "--images", *image_paths,
            "--title", title,
        ]
        if note:
            args += ["--note", note]
        if tags:
            tag_str = ",".join(tags) if isinstance(tags, list) else str(tags)
            args += ["--tags", tag_str]
        if schedule and platform in SCHEDULE_PLATFORMS:
            args += ["--schedule", schedule]

        result = self._run(args, timeout=self.config["timeout_note"])
        result.update({"platform": platform, "images": image_paths})
        return result

    # ---------- 工具 ----------

    def get_name(self) -> str:
        return f"SocialAutoUpload (sau_root={self._sau_root})"

    def __repr__(self):
        return f"<SocialAutoUpload(sau_root={self._sau_root})>"