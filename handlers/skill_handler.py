# handlers/skill_handler.py
"""通用 Skill 处理器：从 core.skill_routes 动态加载并执行 skill。"""

from __future__ import annotations

import importlib
import traceback
from typing import Any, Dict, Optional

from .base import BaseHandler
from core.skill_routes import SKILL_ROUTES


class SkillHandler(BaseHandler):
    """按 skill 名执行。

    与旧版区别：
      - SKILL_MAP 已合并进 SKILL_ROUTES，skill 实现信息（module/class）
        和触发词一起维护，加 skill 只改 core/skill_routes.py
      - kwargs_builder 提供 per-skill 的 intent → execute kwargs 映射
      - 无 kwargs_builder 时走通用映射（text/topic 全传）
    """

    def handle(self, intent: Dict[str, Any]) -> None:
        skill_name = intent.get("params", {}).get("skill")
        if not skill_name:
            self._reply("❌ 未指定技能")
            return

        cfg = SKILL_ROUTES.get(skill_name)
        if not cfg:
            self._reply(f"❌ 技能未注册: {skill_name}")
            return

        module_path = cfg.get("module")
        class_name = cfg.get("class")
        if not module_path or not class_name:
            self._reply(f"❌ 技能 {skill_name} 缺少 module/class 配置")
            return

        # 并发保护
        if getattr(self.app, "_skill_running", False):
            self._reply(
                f"⏳ 有任务正在执行（当前：{self.app._skill_current}）"
            )
            return

        self.app._skill_running = True
        self.app._skill_current = skill_name

        try:
            skill_cls = self._import_skill_class(module_path, class_name)
            skill_instance = skill_cls(self._build_config(skill_name, cfg, intent))
            kwargs = self._build_kwargs(skill_name, cfg, intent)

            self._reply(f"🚀 执行技能 {skill_name}...")
            self._update_status(f"⏳ {skill_name} 运行中...")

            result = skill_instance.execute(**kwargs)

            if result.get("status") == "success":
                self._reply(f"✅ {skill_name} 完成")
                # 回显关键产物
                for key in (
                    "report_file", "audio_file", "image_path",
                    "video_path", "article_path", "preview_path",
                    "saved_to", "repo_url", "article_dir",
                ):
                    v = result.get("result", {}).get(key)
                    if v:
                        self._reply(f"   📄 {key}: {v}")
                self._update_status(f"✅ {skill_name} 完成")
            else:
                err = result.get("error", "未知错误")
                self._reply(f"❌ {skill_name} 失败: {err}")
                self._update_status(f"❌ {skill_name} 失败")

        except Exception as e:
            self._reply(f"❌ 执行异常: {e}")
            self._update_status("❌ 异常")
            traceback.print_exc()
        finally:
            self.app._skill_running = False
            self.app._skill_current = None

    # ---------- 内部 ----------

    @staticmethod
    def _import_skill_class(module_path: str, class_name: str):
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)

    def _build_config(
        self,
        skill_name: str,
        cfg: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构造 skill 实例的 config（只放公共项）。"""
        s = self.app.settings
        config: Dict[str, Any] = {
            "output_dir": str(s.output_dir),
            "log_level": "INFO",
        }
        # config_overrides 只覆盖 execute kwargs，不进 config
        return config

    def _build_kwargs(
        self,
        skill_name: str,
        cfg: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构造 execute() 的 kwargs。

        优先级：
          1. cfg["kwargs_builder"](intent)
          2. 通用映射（text/topic）
        最后叠加 cfg.get("config_overrides", {})
        """
        text = intent.get("prompt") or intent.get("original_text", "")

        builder = cfg.get("kwargs_builder")
        if callable(builder):
            kwargs = builder(intent) or {}
        else:
            kwargs = {"text": text, "topic": text}

        # config_overrides 覆盖 kwargs（比如 github_repo_daily 的 wechat_publish）
        overrides = cfg.get("config_overrides") or {}
        if overrides:
            kwargs.update(overrides)

        return kwargs