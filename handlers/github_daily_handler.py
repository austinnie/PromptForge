# handlers/github_daily_handler.py
"""GitHub 每日仓库推荐处理器"""

import os
from typing import Dict, Any
from .base import BaseHandler


class GitHubDailyHandler(BaseHandler):
    """调用 github_repo_daily skill"""

    def handle(self, intent: Dict[str, Any]) -> None:
        text = intent.get("original_text", "")

        # ✅ 与 _run_skill 共用并发标志，避免和菜单/工具栏同时跑
        if getattr(self.app, "_skill_running", False):
            current = getattr(self.app, "_skill_current", "另一个任务")
            self._reply(
                f"⏳ 有任务正在执行（当前：{current}）\n"
                f"   请等完成后再试——本次请求未入队。"
            )
            return

        self.app._skill_running = True
        self.app._skill_current = "🐙 GitHub 日报"

        # 简单识别"不发布""只生成"等开关
        no_publish = any(k in text for k in ["不发布", "不推送", "只生成", "本地"])
        self._reply("🐙 正在抓取今日 GitHub Trending...")
        self._update_status("🐙 获取仓库列表...")

        try:
            from skills.github_repo_daily import GitHubRepoDaily

            skill = GitHubRepoDaily({
                "wechat_publish": not no_publish,
                "wechat_theme": "newspaper",
            })
            result = skill.execute()

            if result.get("status") != "success":
                self._reply(f"❌ 执行失败: {result.get('error')}")
                self._update_status("❌ 失败")
                return

            r = result["result"]
            self._reply(f"✅ 今日推荐仓库：**{r['repo']}**")
            self._reply(f"🔗 仓库链接：{r['repo_url']}")
            self._reply(f"📄 文章已生成：{os.path.basename(r['article_path'])}")
            if r.get("published"):
                self._reply("📤 已推送到微信公众号草稿箱")
            else:
                self._reply("📄 未推送（已生成到本地）")
            self._update_status(f"✅ 完成 ({r['elapsed']})")

        except Exception as e:
            self._reply(f"❌ 执行异常: {e}")
            self._update_status("❌ 异常")
            import traceback
            traceback.print_exc()
        finally:
            # ✅ 一定要释放，否则后续菜单/按钮会被永久锁住
            self.app._skill_running = False
            self.app._skill_current = None